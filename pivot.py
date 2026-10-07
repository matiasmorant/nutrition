import polars as pl
import numpy as np
from pathlib import Path
from rapidfuzz.distance import Levenshtein
import re, json
from tqdm import tqdm
from glom import glom, Merge, Flatten

def geomean(x):
    x_arr = np.array(x, dtype=float)
    x_valid = x_arr[~np.isnan(x_arr) & (x_arr > 0)]
    if len(x_valid) == 0:
        return np.nan
    return float(np.exp(np.mean(np.log(x_valid))))

def fix_protein(df: pl.DataFrame) -> pl.DataFrame:
    p, n = 'Protein (g)', 'Nitrogen (g)'
    cols = df.columns
    p_expr = pl.col(p) if p in cols else pl.lit(None).alias(p)
    n_expr = pl.col(n) if n in cols else pl.lit(None).alias(n)

    return df.with_columns(
        pl.when(p_expr.is_not_null())
        .then(p_expr)
        .otherwise(n_expr * 6.25)
        .alias(p)
    )

def fix_carb(df: pl.DataFrame) -> pl.DataFrame:
    carbs = [
        'Carbohydrate (g)', 'Sugars (g)', 'Fructose (g)', 'Galactose (g)',
        'Glucose (g)', 'Lactose (g)', 'Maltose (g)', 'Sucrose (g)',
        'Fiber, dietary (g)', 'Fiber, soluble (g)', 'Beta-glucan (g)',
        'Fiber, insoluble (g)', 'High Molecular Weight Dietary Fiber (HMWDF) (g)',
        'Resistant starch (g)', 'Low Molecular Weight Dietary Fiber (LMWDF) (g)',
        'Starch (g)', 'Raffinose (g)', 'Stachyose (g)', 'Verbascose (g)'
    ]
    missing = [c for c in carbs if c not in df.columns]
    if missing:
        df = df.with_columns([pl.lit(None).cast(pl.Float64).alias(c) for c in missing])

    # 1. Sugars calculation
    sugar_cols = ['Fructose (g)', 'Galactose (g)', 'Glucose (g)', 'Lactose (g)', 'Maltose (g)', 'Sucrose (g)']
    sugars_sum = pl.sum_horizontal([pl.col(c).fill_null(0) for c in sugar_cols])
    df = df.with_columns(
        pl.when(pl.col('Sugars (g)').is_not_null())
        .then(pl.col('Sugars (g)'))
        .otherwise(sugars_sum)
        .alias('Sugars (g)')
    )

    # 2. Fiber calculation using geometric mean of column sums
    sum1 = pl.sum_horizontal([pl.col('Fiber, soluble (g)').fill_null(0), pl.col('Fiber, insoluble (g)').fill_null(0)])
    sum2 = pl.sum_horizontal([
        pl.col('High Molecular Weight Dietary Fiber (HMWDF) (g)').fill_null(0),
        pl.col('Low Molecular Weight Dietary Fiber (LMWDF) (g)').fill_null(0)
    ])
    
    fiber_geom = pl.struct([sum1.alias('s1'), sum2.alias('s2')]).map_elements(
        lambda r: geomean([r['s1'], r['s2']]),
        return_dtype=pl.Float64
    )
    df = df.with_columns(
        pl.when(pl.col('Fiber, dietary (g)').is_not_null())
        .then(pl.col('Fiber, dietary (g)'))
        .otherwise(fiber_geom)
        .alias('Fiber, dietary (g)')
    )

    # 3. Total Carbohydrate calculation
    total_carb_cols = ['Sugars (g)', 'Fiber, dietary (g)', 'Starch (g)', 'Raffinose (g)', 'Stachyose (g)', 'Verbascose (g)']
    carbs_sum = pl.sum_horizontal([pl.col(c).fill_null(0) for c in total_carb_cols])
    df = df.with_columns(
        pl.when(pl.col('Carbohydrate (g)').is_not_null())
        .then(pl.col('Carbohydrate (g)'))
        .otherwise(carbs_sum)
        .alias('Carbohydrate (g)')
    )
    return df

def fix_calorie(df: pl.DataFrame) -> pl.DataFrame:
    k = 4.184
    kcal, kj = 'Energy (KCAL)', 'Energy (kJ)'
    spec, gen = 'Energy (Atwater Specific Factors) (KCAL)', 'Energy (Atwater General Factors) (KCAL)'
    c, f, p = 'Carbohydrate (g)', 'Fat (g)', 'Protein (g)'

    for col in [kcal, kj, spec, gen, c, f, p]:
        if col not in df.columns:
            df = df.with_columns(pl.lit(None).cast(pl.Float64).alias(col))

    kj_cal = pl.col(kj) / k
    kcal_col = pl.col(kcal)
    
    geom_kcal_kj = pl.struct([kcal_col.alias('a'), kj_cal.alias('b')]).map_elements(
        lambda r: geomean([r['a'], r['b']]),
        return_dtype=pl.Float64
    )

    atwater_calc = (
        pl.col(c).fill_null(0) * 4 +
        pl.col(f).fill_null(0) * 9 +
        pl.col(p).fill_null(0) * 4
    )

    eqcal = (
        pl.when(geom_kcal_kj.is_not_null() & ~geom_kcal_kj.is_nan())
        .then(geom_kcal_kj)
        .when(pl.col(spec).is_not_null())
        .then(pl.col(spec))
        .when(pl.col(gen).is_not_null())
        .then(pl.col(gen))
        .otherwise(atwater_calc)
    )

    return df.with_columns([
        eqcal.alias(kcal),
        (eqcal * k).alias(kj)
    ])

def merge_foods(names, df: pl.DataFrame, newname=None) -> pl.DataFrame:
    existing = set(df['food'].to_list())
    target_names = [x for x in names if x in existing]
    if not target_names:
        return df

    sub = df.filter(pl.col('food').is_in(target_names))
    num_cols = [c for c in df.columns if c != 'food']
    
    new_row = {'food': newname or target_names[0]}
    for col in num_cols:
        vals = sub[col].drop_nulls().to_numpy()
        new_row[col] = geomean(vals)

    new_df = pl.DataFrame([new_row], schema=df.schema)
    return pl.concat([df.filter(~pl.col('food').is_in(target_names)), new_df], how="diagonal")

def merge_sets(sets):
    merged = []
    for s in sets:
        overlap = s.union(*[x for x in merged if s & x])
        merged = [x for x in merged if not s & x]
        merged.append(overlap)
    return merged

deleteRe = [
    "chicken|poultry|beef|meat|fish|trout|smelt|octopus|owl|caribou|liver|steak|free range|bacon|Whale|seal|Sea lion|turkey|salmon|deer|pork",
    "(with|and) (cheese|milk|oil|margarine|whipped|tomato|onion|carrot|cream|sour|raisin|fruit|dairy|non|mayo|egg|chili|ham|honey)",
    "with (butter|peanuts|soy|fruit)",
]
deleteRe = '.*(' + '|'.join([f"({x})" for x in deleteRe]) + ')'

def replace(pairs, string):
    for r in pairs.items():
        string = string.replace(*r)
    return string

def nutrientmap(n):
    return replace({
        'PUFA 22:5 n-3 (DPA)': 'Omega-3 (DPA)',
        'PUFA 22:5 c': 'Omega-3 (DPA)',
        'PUFA 18:3 n-3 c,c,c (ALA)': 'Omega-3 (ALA)',
        'PUFA 18:3 c': 'Omega-3 (ALA)',
        'PUFA 20:5 n-3 (EPA)': 'Omega-3 (EPA)',
        'PUFA 20:5c': 'Omega-3 (EPA)',
        'PUFA 22:6 n-3 (DHA)': 'Omega-3 (DHA)',
        'PUFA 22:6 c': 'Omega-3 (DHA)',
        'PUFA 18:2 n-6 c,c': 'Omega-6 (Linoleic Acid)',
        'PUFA 18:2 c': 'Omega-6 (Linoleic Acid)',
        'PUFA 18:3 n-6 c,c,c': 'Omega-6 (GLA)',
        'PUFA 20:2 n-6 c,c': 'Omega-6 (Eicosadienoic Acid)',
        'PUFA 20:4 n-6': 'Omega-6 (AA)',
        'PUFA 20:4c': 'Omega-6 (AA)',
        ', by difference': '',
        ', by summation': '',
        'Sugars, Total': 'Sugars',
        'Total Sugars': 'Sugars',
        'Total lipid (fat)': 'Fat',
        'Thiamin': 'Vitamin B1, Thiamin',
        'Riboflavin': 'Vitamin B2, Riboflavin',
        'Niacin': 'Vitamin B3, Niacin',
        'Pantothenic acid': 'Vitamin B5, Pantothenic acid',
        'Vitamin B-6': 'Vitamin B6, Pyridoxine',
        'Folate, total': 'Vitamin B9, Folate',
        'Folate, DFE': 'Vitamin B9, Folate, DFE',
        'Folate, food': 'Vitamin B9, Folate, food',
        'Folic acid': 'Vitamin B9, Folic acid',
        'Tocopherol, beta': 'Vitamin E, beta Tocopherol',
        'Tocopherol, delta': 'Vitamin E, delta Tocopherol',
        'Tocopherol, gamma': 'Vitamin E, gamma Tocopherol',
        'Tocotrienol, alpha': 'Vitamin E, alpha Tocotrienol',
        'Tocotrienol, beta': 'Vitamin E, beta Tocotrienol',
        'Tocotrienol, delta': 'Vitamin E, delta Tocotrienol',
        'Tocotrienol, gamma': 'Vitamin E, gamma Tocotrienol',
        'Calcium, Ca': 'Calcium',
        'Cobalt, Co': 'Cobalt',
        'Copper, Cu': 'Copper',
        'Fluoride, F': 'Fluoride',
        'Iron, Fe': 'Iron',
        'Iodine, I': 'Iodine',
        'Magnesium, Mg': 'Magnesium',
        'Manganese, Mn': 'Manganese',
        'Molybdenum, Mo': 'Molybdenum',
        'Nickel, Ni': 'Nickel',
        'Phosphorus, P': 'Phosphorus',
        'Potassium, K': 'Potassium',
        'Selenium, Se': 'Selenium',
        'Sodium, Na': 'Sodium',
        'Sulfur, S': 'Sulfur',
        'Zinc, Zn': 'Zinc',
        'Fiber, total dietary': 'Fiber, dietary',
        'Total dietary fiber (AOAC 2011.25)': 'Fiber, dietary',
        'Fatty acids, total monounsaturated': 'Fatty acids, monounsaturated',
        'Fatty acids, total polyunsaturated': 'Fatty acids, polyunsaturated',
        'Fatty acids, total saturated': 'Fatty acids, saturated',
        'Fatty acids, total trans': 'Fatty acids, trans',
        'Fatty acids, total trans-monoenoic': 'Fatty acids, trans-monoenoic',
        'Fatty acids, total trans-polyenoic': 'Fatty acids, trans-polyenoic',
        'Choline, total': 'Choline',
        'Vitamin C, total ascorbic acid': 'Vitamin C',
        '(G)': '(g)',
        '(MG)': '(mg)',
        '(UG)': '(µg)',
        '(kcal)': '(KCAL)',
        chr(956): chr(181),
    }, n)

def pivotJSON():
    with open('surveyDownload.json') as p:
        sfoods = json.load(p)['SurveyFoods']
    
    nutrient = {'name': 'nutrient.name', 'unit': 'nutrient.unitName', 'amount': 'amount'}
    nutrients = ('foodNutrients', Merge([(nutrient, lambda x: {f"{x['name']} ({x['unit']})": x['amount']})]))
    data_list = glom(sfoods, [({'food': 'description', 'nutrients': nutrients, 'category': 'wweiaFoodCategory.wweiaFoodCategoryDescription'}, lambda x: {**x.pop('nutrients'), **x})])
    
    data = pl.DataFrame(data_list)

    categories = {
        "Human milk", "Milk, reduced fat", "Milk, whole", "Milk, lowfat", "Milk, nonfat",
        "Flavored milk, whole", "Yogurt, regular", "Yogurt, Greek", "Ice cream and frozen dairy desserts",
        "Flavored milk, lowfat", "Flavored milk, reduced fat", "Flavored milk, nonfat",
        "Milk shakes and other dairy drinks", "Cheese", "Cream cheese, sour cream, whipped cream",
        "Cottage/ricotta cheese", "Butter and animal fats", "Eggs and omelets", "Citrus fruits",
        "Citrus juice", "Other fruit juice", "Dried fruits", "Other fruits and fruit salads",
        "Other vegetables and combinations", "Apples", "Bananas", "Melons", "Grapes", "Mango and papaya",
        "Peaches and nectarines", "Pears", "Pineapple", "Strawberries", "Blueberries and other berries",
        "Apple juice", "Nuts and seeds", "Plant-based milk", "Oatmeal", "Rice",
        "Ready-to-eat cereal, higher sugar (>21.2g/100g)", "Ready-to-eat cereal, lower sugar (=<21.2g/100g)",
        "White potatoes, baked or boiled", "Mashed potatoes and white potato mixtures",
        "French fries and other fried white potatoes", "Other starchy vegetables", "Fried vegetables",
        "Lettuce and lettuce salads", "Vegetable juice", "Other red and orange vegetables",
        "Olives, pickles, pickled vegetables", "Tomato-based condiments", "String beans",
        "Broccoli", "Spinach", "Carrots", "Tomatoes", "Cabbage", "Onions", "Corn",
        "Dips, gravies, other sauces", "Smoothies and grain drinks", "Formula, prepared from powder",
        "Formula, ready-to-feed", "Not included in a food category", "Cream and cream substitutes",
        "Coleslaw, non-lettuce salads", "Shellfish", "Stir-fry and soy-based sauce mixtures",
        "Pasta sauces, tomato-based", "Soy-based condiments", "Fried rice and lo/chow mein",
        "Other dark green vegetables", "Beans, peas, legumes", "Soy and meat-alternative products",
        "Plant-based yogurt", "Mustard and other condiments", "Fruit drinks", "Yeast breads",
        "Turnovers and other grain-based items", "Nutrition bars", "Popcorn", "Pasta, noodles, cooked grains",
        "Grits and other cooked cereals", "Gelatins, ices, sorbets", "Jams, syrups, toppings",
        "Margarine", "Mayonnaise", "Salad dressings and vegetable oils", "Sugars and honey",
        "Sugar substitutes", "Coffee", "Tea", "Soft drinks", "Diet soft drinks",
        "Flavored or carbonated water", "Other diet drinks", "Liquor and cocktails", "Beer", "Wine",
        "Tap water", "Bottled water", "Enhanced water", "Protein and nutritional powders",
        "Sport and energy drinks", "Diet sport and energy drinks"
    }

    data = data.filter(
        pl.col('category').is_in(categories) &
        pl.col('food').is_not_null() &
        ~pl.col('food').str.contains(f"(?i){deleteRe}")
    )

    rename_dict = {col: nutrientmap(col) for col in data.columns if col not in ['food', 'category']}
    data = data.rename(rename_dict).drop('category')

    data = fix_carb(data)
    data = fix_protein(data)
    data = fix_calorie(data)
    return data

def pivot(folder):
    print(f'Pivoting {folder}')
    csv = {x.stem: pl.read_csv(x, infer_schema_length=10000) for x in Path(folder).glob('*.csv')}
    
    csv['nutrient'] = csv['nutrient'].with_columns(
        (pl.col('name') + ' (' + pl.col('unit_name') + ')').map_elements(nutrientmap, return_dtype=pl.Utf8).alias('nutrient')
    )

    csv['food_category'] = csv['food_category'].rename({'description': 'category'})
    csv['food'] = csv['food'].join(
        csv['food_category'].select(['id', 'category']),
        left_on='food_category_id',
        right_on='id',
        how='left'
    )

    categories = {
        'Dairy and Egg Products', 'Spices and Herbs', 'Fats and Oils',
        'Soups, Sauces, and Gravies', 'Breakfast Cereals', 'Fruits and Fruit Juices',
        'Vegetables and Vegetable Products', 'Nut and Seed Products', 'Beverages',
        'Legumes and Legume Products', 'Cereal Grains and Pasta',
        'Meals, Entrees, and Side Dishes', 'Snacks', 'American Indian/Alaska Native Foods'
    }

    def is_not_branded(desc):
        if desc is None:
            return False
        return not any(re.match(r'.*[A-Z]{2,}', w) for w in desc.split())

    csv['food'] = csv['food'].filter(
        pl.col('category').is_in(categories) &
        pl.col('description').is_not_null() &
        pl.col('description').map_elements(is_not_branded, return_dtype=pl.Boolean) &
        ~pl.col('description').str.contains(f"(?i){deleteRe}")
    )

    readable = csv['food_nutrient'].join(
        csv['nutrient'].select(['id', 'nutrient']), left_on='nutrient_id', right_on='id'
    ).join(
        csv['food'].select(['fdc_id', 'description']).rename({'description': 'food'}), left_on='fdc_id', right_on='fdc_id', how='inner'
    ).with_columns(
        pl.col('amount').cast(pl.Float64, strict=False)
    ).filter(
        pl.col('amount') > 0
    )

    big = readable.pivot(index='food', on='nutrient', values='amount', aggregate_function='first')

    reNo = r'(without|no)( added)? (salt|sodium)( added)?'
    reYes = r'(with( added)? (salt|sodium)( added)?)|(added (salt|sodium))|((salt|sodium) added)'

    food_names = big['food'].to_list()
    ws = [x for x in food_names if re.match('.*' + reYes, x)]
    wos = [x for x in food_names if re.match('.*' + reNo, x)]

    matches = []
    for x in ws:
        candidates = [y for y in wos if Levenshtein.distance(re.sub(reNo, '', y), re.sub(reYes, '', x)) < 2]
        if len(candidates) == 1:
            matches.append((x, candidates[0]))

    if 'Sodium (mg)' in big.columns:
        mws_list = [mws for mws, mwos in matches]
        big = big.with_columns(
            pl.when(pl.col('food').is_in(mws_list))
            .then(None)
            .otherwise(pl.col('Sodium (mg)'))
            .alias('Sodium (mg)')
        )

    for mws, mwos in matches:
        new_label = re.sub(r'(, )?' + reNo, '', mwos)
        big = merge_foods([mws, mwos], big, new_label)

    big = fix_carb(big)
    big = fix_protein(big)
    big = fix_calorie(big)
    return big

big = pl.concat([
    pivot('USDA_FoodData_Central_sr_legacy_food'),
    pivot('FoodData_Central_foundation_food_csv_2025-04-24'),
    pivotJSON()
], how='diagonal')

print(len(big))

foodreplace_df = pl.read_csv('foodreplace.csv').fill_null('')
foodreplace_map = {row['from']: row['to'] for row in foodreplace_df.iter_rows(named=True)}

def _normalizeFoodName(x):
    if not x:
        return ""
    x = x.strip()
    x = x[0].upper() + x[1:].lower() if len(x) > 0 else x
    x = replace(foodreplace_map, x)
    x = re.sub(r', raw$', '', x)
    x = re.sub(r',? dried$', ', dry', x)
    x = re.sub(r'Oil, ([\w\s]+)($|,)', r'\1 oil\2', x)
    x = re.sub(r'Seeds, ([\w\s]+)($|,)', r'\1\2', x)
    x = re.sub(r'Nuts, ([\w\s]{4,})', r'\1', x)
    x = re.sub(r'yolks', 'yolk', x)
    return x.strip()

normalizeFoodName = lambda x: _normalizeFoodName(_normalizeFoodName(x))

big = big.with_columns(
    pl.col('food').map_elements(normalizeFoodName, return_dtype=pl.Utf8)
)

print('Merging foods')
def find_and_merge(df: pl.DataFrame) -> pl.DataFrame:
    foods = df['food'].to_list()
    groups = {}
    for f in foods:
        k = f.lower().replace(',', '')
        groups.setdefault(k, []).append(f)
    matches = [set(v) for v in groups.values() if len(v) > 1]
    
    for m in tqdm(matches):
        df = merge_foods(m, df)
    return df

big = find_and_merge(big)
print(len(big))

mergedf = pl.read_csv('foodmerge.csv').filter(pl.col('merge').is_not_null())
mergedf = mergedf.with_columns(pl.col('food').map_elements(normalizeFoodName, return_dtype=pl.Utf8))

for newname, group in tqdm(mergedf.group_by('merge')):
    names = group['food'].to_list()
    big = merge_foods(names, big, normalizeFoodName(newname[0]))

print(len(big))

foodsdelete = Path('foodsdelete.txt').read_text().split('\n')
big = big.filter(~pl.col('food').is_in(foodsdelete)).sort('food')

def digits_round(x, N):
    if x is None or np.isnan(x) or x <= 0:
        return 0.0
    return round(x, N - int(np.floor(np.log10(abs(x)))))

num_cols = [c for c in big.columns if c != 'food']
big = big.with_columns([
    pl.col(c).map_elements(lambda x: digits_round(x, 2), return_dtype=pl.Float64)
    for c in num_cols
])

big = find_and_merge(big)

def check_diet_foods(df: pl.DataFrame):
    with open('diets.json') as p:
        diets = json.load(p)
    foods = glom(diets, Flatten([('foods', ['foodName'])]))
    existing = set(df['food'].to_list())
    return [x for x in foods if x not in existing]