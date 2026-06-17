import pandas as pd

# Lire Form DataCard avec header approprié
df_form = pd.read_excel('DataCard_ImmuneGuard_sprint 6.xlsx', 'Form DataCard')
print('=== Form DataCard columns ===')
print(df_form.columns.tolist())
print()
print('Form DataCard content:')
print(df_form.head(15))
print()

# Lire Valeurs_référence
df_vals = pd.read_excel('DataCard_ImmuneGuard_sprint 6.xlsx', 'Valeurs_référence')
print('=== Valeurs_référence columns ===')
print(df_vals.columns.tolist())
print()
print('Valeurs_référence content:')
print(df_vals.head(10))
print()

# Lire Mapping_C1_C2
df_mapping = pd.read_excel('DataCard_ImmuneGuard_sprint 6.xlsx', 'Mapping_C1_C2', header=None)
print('=== Mapping_C1_C2 structure ===')
print('First 20 rows:')
for i in range(min(20, len(df_mapping))):
    row = df_mapping.iloc[i].tolist()
    clean_row = [str(x)[:50] if pd.notna(x) else "NaN" for x in row]
    print(f'{i}: {clean_row}')