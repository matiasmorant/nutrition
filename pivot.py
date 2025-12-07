import pandas as pd; D=pd.DataFrame
import numpy as np
from pathlib import Path
from rapidfuzz.distance import Levenshtein
import re, json
from collections import Counter
from tqdm import tqdm

def merge_foods(names, df, newname=None):
  names=list(names)
  newfood=df.loc[names].apply(lambda x: np.exp(np.log(x).mean()))
  newfood.name= newname or names[0]
  return pd.concat([df.drop(index=names), newfood.to_frame().T])

def merge_sets(sets):
    merged = []
    for s in sets:
        overlap = s.union(*[x for x in merged if s & x])
        merged = [x for x in merged if not s & x]
        merged.append(overlap)
    return merged

def pivot(folder):
  print(f'Pivoting {folder}')
  csv={x.name.replace('.csv',''): pd.read_csv(x) for x in Path(folder).glob('*.csv')}
  csv['nutrient']=csv['nutrient'].set_index('id').apply(lambda x: f"{x['name']} ({x['unit_name']})", axis=1)\
     .map(lambda x:{'PUFA 22:5 n-3 (DPA) (G)'       :'Omega-3 (DPA) (G)',
         'PUFA 18:3 n-3 c,c,c (ALA) (G)' :'Omega-3 (ALA) (G)',
         'PUFA 20:5 n-3 (EPA) (G)'       :'Omega-3 (EPA) (G)',
         'PUFA 22:6 n-3 (DHA) (G)'       :'Omega-3 (DHA) (G)',
         'PUFA 18:2 n-6 c,c (G)'         :'Omega-6 (Linoleic Acid) (G)',
         'PUFA 18:3 n-6 c,c,c (G)'       :'Omega-6 (GLA) (G)',
         'PUFA 20:2 n-6 c,c (G)'         :'Omega-6 (Eicosadienoic Acid) (G)',
         'PUFA 20:4 n-6 (G)'             :'Omega-6 (AA) (G)',
         'Carbohydrate, by difference (G)':'Carbohydrate (G)',
         'Sugars, Total (G)'             :'Sugars (G)',
         'Total lipid (fat) (G)'         :'Fat (G)',
         'Thiamin (MG)'          :'Vitamin B1, Thiamin (MG)',
         'Riboflavin (MG)'       :'Vitamin B2, Riboflavin (MG)',
         'Niacin (MG)'           :'Vitamin B3, Niacin (MG)',
         'Pantothenic acid (MG)' :'Vitamin B5, Pantothenic acid (MG)',
         'Vitamin B-6 (MG)'      :'Vitamin B6, Pyridoxine (MG)',
         'Folate, total (UG)'    :'Vitamin B9, Folate (UG)',
         'Folate, DFE (UG)'      :'Vitamin B9, Folate, DFE (UG)',
         'Folate, food (UG)'     :'Vitamin B9, Folate, food (UG)',
         'Folic acid (UG)'       :'Vitamin B9, Folic acid (UG)',
         'Tocopherol, beta (MG)'   :'Vitamin E, beta Tocopherol (MG)',
         'Tocopherol, delta (MG)'  :'Vitamin E, delta Tocopherol (MG)',
         'Tocopherol, gamma (MG)'  :'Vitamin E, gamma Tocopherol (MG)',
         'Tocotrienol, alpha (MG)' :'Vitamin E, alpha Tocotrienol (MG)',
         'Tocotrienol, beta (MG)'  :'Vitamin E, beta Tocotrienol (MG)',
         'Tocotrienol, delta (MG)' :'Vitamin E, delta Tocotrienol (MG)',
         'Tocotrienol, gamma (MG)' :'Vitamin E, gamma Tocotrienol (MG)',
         'Calcium, Ca (MG)':'Calcium (MG)',
         'Copper, Cu (MG)':'Copper (MG)',
         'Fluoride, F (UG)':'Fluoride (UG)',
         'Iron, Fe (MG)':'Iron (MG)',
         'Magnesium, Mg (MG)':'Magnesium (MG)',
         'Manganese, Mn (MG)':'Manganese (MG)',
         'Phosphorus, P (MG)':'Phosphorus (MG)',
         'Potassium, K (MG)':'Potassium (MG)',
         'Selenium, Se (UG)':'Selenium (UG)',
         'Sodium, Na (MG)':'Sodium (MG)',
         'Zinc, Zn (MG)':'Zinc (MG)',
         'Fiber, total dietary (G)':'Fiber, dietary (G)',
         'Fatty acids, total monounsaturated (G)':'Fatty acids, monounsaturated (G)',
         'Fatty acids, total polyunsaturated (G)':'Fatty acids, polyunsaturated (G)',
         'Fatty acids, total saturated (G)':'Fatty acids, saturated (G)',
         'Fatty acids, total trans (G)':'Fatty acids, trans (G)',
         'Fatty acids, total trans-monoenoic (G)':'Fatty acids, trans-monoenoic (G)',
         'Fatty acids, total trans-polyenoic (G)':'Fatty acids, trans-polyenoic (G)',
         'Choline, total (MG)':'Choline (MG)',
         'Vitamin C, total ascorbic acid (MG)':'Vitamin C (MG)',
         }.get(x,x).replace('(G)','(g)').replace('(MG)','(mg)').replace('(UG)','(μg)'))

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
  csv['food']=csv['food'][csv['food'].apply(lambda x: (x['category'] in categories) and pd.notna(x['description']) and not branded(x['description']) and not re.match(".*(chicken|beef|meat|fish|liver|steak|free range|bacon|Whale|Sea lion|turkey|salmon|deer)",x['description'],re.I), axis=1)]

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

legacy=pivot('USDA_FoodData_Central_sr_legacy_food')
foundation=pivot('FoodData_Central_foundation_food_csv_2025-04-24')
# foundation.index=['👑 '+x for x in foundation.index]
big=pd.concat([legacy,foundation])

normalizecasing= lambda x: x[0].upper()+x[1:].lower()
big.index=big.index.map(lambda x: x.strip()).map(normalizecasing)

# 3916
print(f'Merging foods')
matches=big.index.groupby([x.lower().replace(',','') for x in big.index])
matches=[set(v) for k,v in matches.items() if len(v)>1]
for m in tqdm(matches): big = merge_foods(m,big)

# match=[[x,[y for y in big.index if 0<Levenshtein.distance(x,y)<3]] for x in tqdm(big.index)]
# match=[{x,*y} for x,y in match if y]

# big.index.sort_values().to_frame().to_csv('foodmerge.csv',index=False)
mergedf=pd.read_csv('foodmerge.csv').dropna(subset=['merge'])
mergedf['food']=mergedf['food'].map(normalizecasing)
for newname, names in tqdm(mergedf['food'].groupby(mergedf['merge'])): big=merge_foods(names,big,newname)
big=big.sort_index()

def digits_round(x,N):return round(x, N - int(np.floor(np.log10(abs(x)))))
big=big.applymap(lambda x: digits_round(x,2), na_action='ignore')

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