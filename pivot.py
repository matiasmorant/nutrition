import pandas as pd; D=pd.DataFrame
import numpy as np
from pathlib import Path
from rapidfuzz.distance import Levenshtein
import re, json
from collections import Counter
from tqdm import tqdm
from glom import glom, Iter, T, Fold, Flatten, Merge

def merge_foods(names, df, newname=None):
  names=[x for x in names if x in df.index]
  if not names: return df
  newfood=df.loc[names].apply(lambda x: np.exp(np.log(x[x>0]).mean()))
  newfood.name= newname or names[0]
  return pd.concat([df.drop(index=names), newfood.to_frame().T])

def merge_sets(sets):
  merged = []
  for s in sets:
    overlap = s.union(*[x for x in merged if s & x])
    merged = [x for x in merged if not s & x]
    merged.append(overlap)
  return merged

deleteRe=[
"chicken|poultry|beef|meat|fish|liver|steak|free range|bacon|Whale|Sea lion|turkey|salmon|deer|pork",
"(with|and) (cheese|milk|oil|margarine|tomato|cream|sour|raisin|dairy|non|mayo|egg|chili)",
"with (butter|peanuts|soy)",
]
deleteRe='|'.join([f"({x})"for x in deleteRe])
deleteRe=f".*({deleteRe})"

def replace(pairs,string):
  for r in pairs.items(): string=string.replace(*r)
  return string

def nutrientmap(n):
  return replace({
    'PUFA 22:5 n-3 (DPA)'       :'Omega-3 (DPA)',
    'PUFA 22:5 c'               :'Omega-3 (DPA)',
    'PUFA 18:3 n-3 c,c,c (ALA)' :'Omega-3 (ALA)',
    'PUFA 18:3 c'               :'Omega-3 (ALA)',
    'PUFA 20:5 n-3 (EPA)'       :'Omega-3 (EPA)',
    'PUFA 20:5c'                :'Omega-3 (EPA)',
    'PUFA 22:6 n-3 (DHA)'       :'Omega-3 (DHA)',
    'PUFA 22:6 c'               :'Omega-3 (DHA)',
    'PUFA 18:2 n-6 c,c'         :'Omega-6 (Linoleic Acid)',
    'PUFA 18:2 c'               :'Omega-6 (Linoleic Acid)',
    'PUFA 18:3 n-6 c,c,c'       :'Omega-6 (GLA)',
    'PUFA 20:2 n-6 c,c'         :'Omega-6 (Eicosadienoic Acid)',
    'PUFA 20:4 n-6'             :'Omega-6 (AA)',
    'PUFA 20:4c'                :'Omega-6 (AA)',
    # 'PUFA 18:2 CLAs'            :,
    # 'PUFA 18:2 i'               :,
    # 'PUFA 18:3i'                :,
    # 'PUFA 20:2 c'               :,
    # 'PUFA 20:3'                 :,
    # 'PUFA 20:3 c'               :,
    # 'PUFA 20:3 n-3'             :,
    # 'PUFA 20:3 n-6'             :,
    # 'PUFA 21:5'                 :,
    # 'PUFA 22:2'                 :,
    # 'PUFA 22:3'                 :,
    # 'PUFA 22:4'                 :,
    ', by difference':'',
    ', by summation':'',
    'Sugars, Total'             :'Sugars',
    'Total lipid (fat)'         :'Fat',
    'Thiamin'          :'Vitamin B1, Thiamin',
    'Riboflavin'       :'Vitamin B2, Riboflavin',
    'Niacin'           :'Vitamin B3, Niacin',
    'Pantothenic acid' :'Vitamin B5, Pantothenic acid',
    'Vitamin B-6'      :'Vitamin B6, Pyridoxine',
    'Folate, total'    :'Vitamin B9, Folate',
    'Folate, DFE'      :'Vitamin B9, Folate, DFE',
    'Folate, food'     :'Vitamin B9, Folate, food',
    'Folic acid'       :'Vitamin B9, Folic acid',
    'Tocopherol, beta'   :'Vitamin E, beta Tocopherol',
    'Tocopherol, delta'  :'Vitamin E, delta Tocopherol',
    'Tocopherol, gamma'  :'Vitamin E, gamma Tocopherol',
    'Tocotrienol, alpha' :'Vitamin E, alpha Tocotrienol',
    'Tocotrienol, beta'  :'Vitamin E, beta Tocotrienol',
    'Tocotrienol, delta' :'Vitamin E, delta Tocotrienol',
    'Tocotrienol, gamma' :'Vitamin E, gamma Tocotrienol',
    'Calcium, Ca'   :'Calcium',
    'Cobalt, Co'    :'Cobalt',
    'Copper, Cu'    :'Copper',
    'Fluoride, F'   :'Fluoride',
    'Iron, Fe'      :'Iron',
    'Iodine, I'     :'Iodine',
    'Magnesium, Mg' :'Magnesium',
    'Manganese, Mn' :'Manganese',
    'Molybdenum, Mo':'Molybdenum',
    'Nickel, Ni'    :'Nickel',
    'Phosphorus, P' :'Phosphorus',
    'Potassium, K'  :'Potassium',
    'Selenium, Se'  :'Selenium',
    'Sodium, Na'    :'Sodium',
    'Sulfur, S'     :'Sulfur',
    'Zinc, Zn'      :'Zinc',
    'Fiber, total dietary':'Fiber, dietary',
    'Fatty acids, total monounsaturated':'Fatty acids, monounsaturated',
    'Fatty acids, total polyunsaturated':'Fatty acids, polyunsaturated',
    'Fatty acids, total saturated':'Fatty acids, saturated',
    'Fatty acids, total trans':'Fatty acids, trans',
    'Fatty acids, total trans-monoenoic':'Fatty acids, trans-monoenoic',
    'Fatty acids, total trans-polyenoic':'Fatty acids, trans-polyenoic',
    'Choline, total':'Choline',
    'Vitamin C, total ascorbic acid':'Vitamin C',
    '(G)'   :'(g)',
    '(MG)'  :'(mg)',
    '(UG)'  :'(µg)',
    '(kcal)':'(KCAL)',
    chr(956):chr(181),
  },n)

def pivotJSON():
    with open('surveyDownload.json') as p: sfoods=json.load(p)['SurveyFoods']
    nutrient={'name':'nutrient.name','unit':'nutrient.unitName','amount':'amount'}
    # nutrients=('foodNutrients',Fold([nutrient], init=dict, op=lambda r,x: {**r, f"{x['name']} ({x['unit']})": x['amount']}) )
    nutrients=('foodNutrients',Merge([(nutrient, lambda x: {f"{x['name']} ({x['unit']})": x['amount']})]) )
    # data=glom(sfoods, {'food':['description'],'nutrients':[nutrients], 'category':['wweiaFoodCategory.wweiaFoodCategoryDescription']})
    # return D(data['nutrients'],index=data['food'])
    data=D(glom(sfoods, [({'food':'description','nutrients':nutrients, 'category':'wweiaFoodCategory.wweiaFoodCategoryDescription'},lambda x: {**x.pop('nutrients'),**x})]))
    categories = {
    # dairy
    "Human milk",
    "Milk, reduced fat","Milk, whole","Milk, lowfat","Milk, nonfat",
    "Flavored milk, whole",
    "Yogurt, regular","Yogurt, Greek",
    "Ice cream and frozen dairy desserts",
    "Flavored milk, lowfat","Flavored milk, reduced fat","Flavored milk, nonfat",
    "Milk shakes and other dairy drinks",
    "Cheese",
    "Cream cheese, sour cream, whipped cream",
    "Cottage/ricotta cheese",
    "Butter and animal fats",
    "Eggs and omelets",
    # vegetables
    "Citrus fruits",
    "Citrus juice","Other fruit juice",
    "Dried fruits",
    "Other fruits and fruit salads",
    "Other vegetables and combinations",
    "Apples","Bananas","Melons","Grapes","Mango and papaya",
    "Peaches and nectarines","Pears","Pineapple","Strawberries",
    "Blueberries and other berries",
    "Apple juice",
    "Nuts and seeds",
    "Plant-based milk",
    "Oatmeal",
    "Rice",
    "Ready-to-eat cereal, higher sugar (>21.2g/100g)",
    "Ready-to-eat cereal, lower sugar (=<21.2g/100g)",
    "White potatoes, baked or boiled",
    "Mashed potatoes and white potato mixtures",
    "French fries and other fried white potatoes",
    "Other starchy vegetables",
    "Fried vegetables",
    "Lettuce and lettuce salads",
    "Vegetable juice",
    "Other red and orange vegetables",
    "Olives, pickles, pickled vegetables",
    "Tomato-based condiments",
    "String beans",
    "Broccoli","Spinach","Carrots","Tomatoes","Cabbage","Onions",
    "Corn",
    "Dips, gravies, other sauces",
    "Smoothies and grain drinks",
    "Formula, prepared from powder","Formula, ready-to-feed",
    "Not included in a food category",
    "Cream and cream substitutes",
    "Coleslaw, non-lettuce salads",
    "Shellfish",
    "Stir-fry and soy-based sauce mixtures",
    "Pasta sauces, tomato-based",
    "Soy-based condiments",
    "Fried rice and lo/chow mein",
    "Other dark green vegetables",
    "Beans, peas, legumes",
    "Soy and meat-alternative products",
    "Plant-based yogurt",
    "Mustard and other condiments",
    "Fruit drinks",
    "Yeast breads",
    "Turnovers and other grain-based items",
    "Nutrition bars",
    "Popcorn",
    "Pasta, noodles, cooked grains",
    "Grits and other cooked cereals",
    "Gelatins, ices, sorbets",
    "Jams, syrups, toppings",
    "Margarine",
    "Mayonnaise",
    "Salad dressings and vegetable oils",
    "Sugars and honey",
    "Sugar substitutes",
    "Coffee","Tea",
    "Soft drinks",
    "Diet soft drinks",
    "Flavored or carbonated water",
    "Other diet drinks",
    "Liquor and cocktails",
    "Beer","Wine",
    "Tap water","Bottled water",
    "Enhanced water",
    "Protein and nutritional powders",
    "Sport and energy drinks",
    "Diet sport and energy drinks",
    }
    data=data[data.apply(lambda x: (x['category'] in categories) and pd.notna(x['food']) and not re.match(deleteRe,x['food'],re.I), axis=1)]
    data=data.rename(columns=nutrientmap)

    return data.set_index('food').drop(columns=['category'])

def pivot(folder):
  print(f'Pivoting {folder}')
  csv={x.name.replace('.csv',''): pd.read_csv(x) for x in Path(folder).glob('*.csv')}
  csv['nutrient']=csv['nutrient'].set_index('id').apply(lambda x: f"{x['name']} ({x['unit_name']})", axis=1).map(nutrientmap)

  csv['food_category']=csv['food_category'].set_index('id')
  csv['food']=csv['food'].set_index('fdc_id').join(csv['food_category'].rename(columns={'description':'category'}),on='food_category_id')[['description','category']]
  categories={
  'Dairy and Egg Products',
  'Spices and Herbs',
  'Fats and Oils',
  'Soups, Sauces, and Gravies',
  'Breakfast Cereals',
  'Fruits and Fruit Juices',
  'Vegetables and Vegetable Products',
  'Nut and Seed Products',
  'Beverages',
  'Legumes and Legume Products',
  'Cereal Grains and Pasta',
  'Meals, Entrees, and Side Dishes',
  'Snacks', #(some meat here)
  'American Indian/Alaska Native Foods' #(some meat here)
  }
  def branded(food): return any(bool(re.match(r'.*[A-Z]{2,}',w)) for w in food.split())
  csv['food']=csv['food'][csv['food'].apply(lambda x: (x['category'] in categories) and pd.notna(x['description']) and not branded(x['description']) and not re.match(deleteRe,x['description'],re.I), axis=1)]

  readable=csv['food_nutrient']\
    .join(csv['nutrient'].to_frame('nutrient'), on='nutrient_id')\
    .join(csv['food']['description'].to_frame('food'), on='fdc_id', how='inner')
  readable=readable[readable['amount']>0]
  big=readable.pivot_table(columns='nutrient',index='food',values='amount')

  # SALT
  reNo=r'(without|no)( added)? (salt|sodium)( added)?'
  reYes=r'(with( added)? (salt|sodium)( added)?)|(added (salt|sodium))|((salt|sodium) added)'
  ws =big[big.index.str.match('.*(with( added)? (salt|sodium)( added)?)|(added (salt|sodium))|((salt|sodium) added)')]
  wos=big[big.index.str.match('.*(without|no)( added)? (salt|sodium)( added)?')]
  matches=[[x,[y for y in wos.index if Levenshtein.distance(re.sub(reNo,'',y),re.sub(reYes,'',x))<2]] for x in ws.index]
  matches=[[k,v[0]]for k,v in matches if len(v)==1]
  #merge
  def nutdiff(pair):nut=big.loc[pair];return nut.T[nut.apply(lambda r: len(r.drop_duplicates())!=1)]
  diffs=[(m,nutdiff(m))for m in matches]
  nd=[(m,d) for m,d in diffs if len(d)!=1]
  for m,d in nd: big.loc[m[1]].update(d.drop('Sodium (mg)',errors='ignore').apply(lambda x: x.fillna(x.sum()), axis=1).apply(lambda x: x.prod()**.5, axis=1))
  discard=[mws for mws,mwos in matches]
  rename={mwos: re.sub(r'(, )?'+reNo,'',mwos) for mws,mwos in matches}
  big=big.drop(index=discard).rename(index=rename)

  return big

big=pd.concat([
  pivot('USDA_FoodData_Central_sr_legacy_food'),
  pivot('FoodData_Central_foundation_food_csv_2025-04-24'),
  pivotJSON()
])
print(len(big))

foodreplace=pd.read_csv('foodreplace.csv').fillna('')
foodreplace={x['from']:x['to'] for _, x in foodreplace.iterrows()}

def _normalizeFoodName(x):
  x=x.strip()
  x=x[0].upper()+x[1:].lower()
  x=replace(foodreplace,x)
  x=re.sub(r', raw$','',x)
  x=re.sub(r'Oil, ([\w\s]+)($|,)',r'\1 oil\2',x)
  return x.strip()
normalizeFoodName=lambda x: _normalizeFoodName(_normalizeFoodName(x))

big.index=big.index.map(normalizeFoodName)

big=big.replace(0,np.nan)
# 3916
print(f'Merging foods')
def find_and_merge(big):
  matches=big.index.groupby([x.lower().replace(',','') for x in big.index])
  matches=[set(v) for k,v in matches.items() if len(v)>1]
  for m in tqdm(matches): big = merge_foods(m,big)
  return big
big=find_and_merge(big)
print(len(big))

# match=[[x,[y for y in big.index if 0<Levenshtein.distance(x,y)<3]] for x in tqdm(big.index)]
# match=[{x,*y} for x,y in match if y]

# big.index.sort_values().to_frame().to_csv('foodmerge.csv',index=False)
mergedf=pd.read_csv('foodmerge.csv').dropna(subset=['merge'])
mergedf['food']=mergedf['food'].map(normalizeFoodName)
for newname, names in tqdm(mergedf['food'].groupby(mergedf['merge'])): big=merge_foods(names,big,normalizeFoodName(newname))
print(len(big))

foodsdelete=Path('foodsdelete.txt').read_text().split('\n')
big=big.drop(index=foodsdelete, errors='ignore')

big=big.sort_index()

def digits_round(x,N):return round(x, N - int(np.floor(np.log10(abs(x))))) if x>0 else 0.0
big=big.applymap(lambda x: digits_round(x,2), na_action='ignore')

big=find_and_merge(big)

def check_diet_foods(big):
  with open('diets.json') as p: diets=json.load(p)
  foods=glom(diets, Flatten([('foods',['foodName'])]))
  return [x for x in foods if x not in big.index]

# with open('foods.txt','w') as p: p.write('\n'.join(big.index))
# rec=[x.dropna().to_dict() for _, x in big.reset_index(names='name').iterrows()]
# with open('foodnutrient.json','w') as f: f.write(json.dumps(rec))

# big[big.index.str.startswith('Chickpea')]

# # Dairy and Egg Products
# # Spices and Herbs

# # Fats and Oils
# # Soups, Sauces, and Gravies

# # Breakfast Cereals
# # Fruits and Fruit Juices

# # Vegetables and Vegetable Products
# # Nut and Seed Products

# # Beverages
# # Finfish and Shellfish Products
# # Legumes and Legume Products



# # Cereal Grains and Pasta

# # Meals, Entrees, and Side Dishes
# # Snacks (some meat here)
# # American Indian/Alaska Native Foods  (some meat here)

# # why Biotin B7|H missing? -> no Biotin in Legacy, only Foundation 
# old=set("""
# Energy (KCAL)
# Energy (kJ)
# Protein (g)
# Carbohydrate (g)
# Fat (g)
# Fatty acids, total monounsaturated (g)
# Fatty acids, total polyunsaturated (g)
# Fatty acids, total saturated (g)
# Fatty acids, total trans (g)
# Fatty acids, total trans-monoenoic (g)
# Fatty acids, total trans-polyenoic (g)
# Alanine (g)
# Alcohol, ethyl (g)
# Arginine (g)
# Ash (g)
# Aspartic acid (g)
# Beta-sitosterol (mg)
# Betaine (mg)
# Caffeine (mg)
# Calcium, Ca (mg)
# Campesterol (mg)
# Carotene, alpha (UG)
# Carotene, beta (UG)
# Cholesterol (mg)
# Choline, total (mg)
# Copper, Cu (mg)
# Cryptoxanthin, beta (UG)
# Cystine (g)
# Fiber, total dietary (g)
# Fluoride, F (UG)
# Vitamin B9, Folate, DFE (UG)
# Vitamin B9, Folate, food (UG)
# Vitamin B9, Folate (UG)
# Vitamin B9, Folic acid (UG)
# Fructose (g)
# Galactose (g)
# Glucose (g)
# Glutamic acid (g)
# Glycine (g)
# Histidine (g)
# Hydroxyproline (g)
# Iron, Fe (mg)
# Isoleucine (g)
# Lactose (g)
# Leucine (g)
# Lutein + zeaxanthin (UG)
# Lycopene (UG)
# Lysine (g)
# MUFA 14:1 (g)
# MUFA 15:1 (g)
# MUFA 16:1 (g)
# MUFA 16:1 c (g)
# MUFA 17:1 (g)
# MUFA 18:1 (g)
# MUFA 18:1 c (g)
# MUFA 18:1-11 t (18:1t n-7) (g)
# MUFA 20:1 (g)
# MUFA 22:1 (g)
# MUFA 22:1 c (g)
# MUFA 24:1 c (g)
# Magnesium, Mg (mg)
# Maltose (g)
# Manganese, Mn (mg)
# Methionine (g)
# Vitamin B3, Niacin (mg)
# PUFA 18:2 (g)
# PUFA 18:2 CLAs (g)
# PUFA 18:2 i (g)
# Omega-6 (Linoleic Acid) (g)
# PUFA 18:3 (g)
# Omega-3 (ALA) (g)
# Omega-6 (GLA) (g)
# PUFA 18:3i (g)
# PUFA 18:4 (g)
# Omega-6 (Eicosadienoic Acid) (g)
# PUFA 20:3 (g)
# PUFA 20:3 n-3 (g)
# PUFA 20:4 (g)
# Omega-6 (AA) (g)
# Omega-3 (EPA) (g)
# PUFA 21:5 (g)
# PUFA 22:4 (g)
# Omega-3 (DPA) (g)
# Omega-3 (DHA) (g)
# PUFA 2:4 n-6 (g)
# Vitamin B5, Pantothenic acid (mg)
# Phenylalanine (g)
# Phosphorus, P (mg)
# Phytosterols (mg)
# Potassium, K (mg)
# Proline (g)
# Retinol (UG)
# Vitamin B2, Riboflavin (mg)
# SFA 10:0 (g)
# SFA 12:0 (g)
# SFA 13:0 (g)
# SFA 14:0 (g)
# SFA 15:0 (g)
# SFA 16:0 (g)
# SFA 17:0 (g)
# SFA 18:0 (g)
# SFA 20:0 (g)
# SFA 22:0 (g)
# SFA 24:0 (g)
# SFA 4:0 (g)
# SFA 6:0 (g)
# SFA 8:0 (g)
# Selenium, Se (UG)
# Serine (g)
# Sodium, Na (mg)
# Starch (g)
# Stigmasterol (mg)
# Sucrose (g)
# Sugars (g)
# TFA 16:1 t (g)
# TFA 18:1 t (g)
# TFA 18:2 t not further defined (g)
# TFA 18:2 t,t (g)
# TFA 22:1 t (g)
# Theobromine (mg)
# Vitamin B1, Thiamin (mg)
# Threonine (g)
# Vitamin E, beta Tocopherol (mg)
# Vitamin E, delta Tocopherol (mg)
# Vitamin E, gamma Tocopherol (mg)
# Vitamin E, alpha Tocotrienol (mg)
# Vitamin E, beta Tocotrienol (mg)
# Vitamin E, delta Tocotrienol (mg)
# Vitamin E, gamma Tocotrienol (mg)
# Tryptophan (g)
# Tyrosine (g)
# Valine (g)
# Vitamin A, IU (IU)
# Vitamin A, RAE (UG)
# Vitamin B-12 (UG)
# Vitamin B-12, added (UG)
# Vitamin B6, Pyridoxine (mg)
# Vitamin C, total ascorbic acid (mg)
# Vitamin D (D2 + D3) (UG)
# Vitamin D (D2 + D3), International Units (IU)
# Vitamin D2 (ergocalciferol) (UG)
# Vitamin D3 (cholecalciferol) (UG)
# Vitamin K (Dihydrophylloquinone) (UG)
# Vitamin K (Menaquinone-4) (UG)
# Vitamin K (phylloquinone) (UG)
# Zinc, Zn (mg)
# """.split('\n'))

# new=set(map(lambda x: x.strip(),"""
# Energy (KCAL)
# Energy (kJ)
# Protein (g)
#   Histidine (g)
#   Isoleucine (g)
#   Leucine (g)
#   Lysine (g)
#   Methionine (g)
#   Phenylalanine (g)
#   Threonine (g)
#   Tryptophan (g)
#   Valine (g)
#   Alanine (g)
#   Arginine (g)
#   Aspartic acid (g)
#   Cystine (g)
#   Glutamic acid (g)
#   Glycine (g)
#   Hydroxyproline (g)
#   Proline (g)
#   Serine (g)
#   Tyrosine (g)
# Carbohydrate (g)
#   Sugars (g)
#     Fructose (g)
#     Galactose (g)
#     Glucose (g)
#     Lactose (g)
#     Maltose (g)
#     Sucrose (g)
#   Starch (g)
#   Fiber, total dietary (g)
# Fat (g)
#   Fatty acids, total monounsaturated (g)
#     MUFA 14:1 (g)
#     MUFA 15:1 (g)
#     MUFA 16:1 (g)
#     MUFA 16:1 c (g)
#     MUFA 17:1 (g)
#     MUFA 18:1 (g)
#     MUFA 18:1 c (g)
#     MUFA 18:1-11 t (18:1t n-7) (g)
#     MUFA 20:1 (g)
#     MUFA 22:1 (g)
#     MUFA 22:1 c (g)
#     MUFA 24:1 c (g)
#   Fatty acids, total polyunsaturated (g)
#     Omega-3 (ALA) (g)
#     Omega-3 (EPA) (g)
#     Omega-3 (DPA) (g)
#     Omega-3 (DHA) (g)
#     Omega-6 (Linoleic Acid) (g)
#     Omega-6 (GLA) (g)
#     Omega-6 (Eicosadienoic Acid) (g)
#     Omega-6 (AA) (g)
#     PUFA 18:2 (g)
#     PUFA 18:2 CLAs (g)
#     PUFA 18:2 i (g)
#     PUFA 18:3 (g)
#     PUFA 18:3i (g)
#     PUFA 18:4 (g)
#     PUFA 20:3 (g)
#     PUFA 20:3 n-3 (g)
#     PUFA 20:4 (g)
#     PUFA 21:5 (g)
#     PUFA 22:4 (g)
#     PUFA 2:4 n-6 (g)
#   Fatty acids, total saturated (g)
#     SFA 10:0 (g)
#     SFA 12:0 (g)
#     SFA 13:0 (g)
#     SFA 14:0 (g)
#     SFA 15:0 (g)
#     SFA 16:0 (g)
#     SFA 17:0 (g)
#     SFA 18:0 (g)
#     SFA 20:0 (g)
#     SFA 22:0 (g)
#     SFA 24:0 (g)
#     SFA 4:0 (g)
#     SFA 6:0 (g)
#     SFA 8:0 (g)
#   Fatty acids, total trans (g)
#     Fatty acids, total trans-monoenoic (g)
#       TFA 16:1 t (g)
#       TFA 18:1 t (g)
#       TFA 22:1 t (g)
#     Fatty acids, total trans-polyenoic (g)
#       TFA 18:2 t not further defined (g)
#       TFA 18:2 t,t (g)
# Vitamins
#   Choline, total (mg)
#   Vitamin E, added (mg)
#   Vitamin E (alpha-tocopherol) (mg)   x1
#   Vitamin E, beta Tocopherol (mg)     x0.3
#   Vitamin E, gamma Tocopherol (mg)    x0.1
#   Vitamin E, delta Tocopherol (mg)    x0.02
#   Vitamin E, alpha Tocotrienol (mg)   x0.25
#   Vitamin E, beta Tocotrienol (mg)    x0.05
#   Vitamin E, gamma Tocotrienol (mg)   x0.02
#   Vitamin E, delta Tocotrienol (mg)   x0.0
#   Vitamin A, IU (IU)
#   Vitamin A, RAE (μG)
#     Retinol (μG)              1 UG RAE
#     Cryptoxanthin, beta (μG)  1/24 UG RAE
#     Carotene, alpha (μG)      1/24 UG RAE
#     Carotene, beta (μG)       1/12 UG RAE
#   Vitamin B1, Thiamin (mg)
#   Vitamin B2, Riboflavin (mg)
#   Vitamin B3, Niacin (mg)
#   Vitamin B5, Pantothenic acid (mg)
#   Vitamin B6, Pyridoxine (mg)
#   Vitamin B9, Folate (μG)
#   Vitamin B9, Folate, DFE (μG)
#   Vitamin B9, Folate, food (μG)
#   Vitamin B9, Folic acid (μG)
#   Vitamin B-12 (μG)
#   Vitamin B-12, added (μG)
#   Vitamin C, total ascorbic acid (mg)
#   Vitamin D (D2 + D3) (μG)
#   Vitamin D (D2 + D3), International Units (IU)
#   Vitamin D2 (ergocalciferol) (μG)
#   Vitamin D3 (cholecalciferol) (μG)
#   Vitamin E (alpha-tocopherol) (mg)
#   Vitamin E, added (mg)
#   Vitamin K (Dihydrophylloquinone) (μG)
#   Vitamin K (Menaquinone-4) (μG)
#   Vitamin K (phylloquinone) (μG)
# Minerals
#   Calcium, Ca (mg)
#   Copper, Cu (mg)
#   Fluoride, F (μG)
#   Iron, Fe (mg)
#   Magnesium, Mg (mg)
#   Manganese, Mn (mg)
#   Phosphorus, P (mg)
#   Potassium, K (mg)
#   Selenium, Se (μG)
#   Sodium, Na (mg)
#   Zinc, Zn (mg)
# Alcohol, ethyl (g)
# Beta-sitosterol (mg)
# Betaine (mg)
# Caffeine (mg)
# Campesterol (mg)
# Cholesterol (mg)
# Lutein + zeaxanthin (μG)
# Lycopene (μG)
# Phytosterols (mg)
# Stigmasterol (mg)
# Theobromine (mg)
# """.split('\n')))

# # Chicken, meatless