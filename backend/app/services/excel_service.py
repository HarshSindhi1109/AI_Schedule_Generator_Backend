import pandas as pd
import re
import io
from typing import List, Dict

pd.set_option('display.max_colwidth', None)

def extract_courses_from_excel(file_bytes: bytes) -> List[Dict]:
    """
    Reads Excel file bytes and extracts course details as list of dicts.
    """

    df = pd.read_excel(io.BytesIO(file_bytes), header=[1, 2, 3])

    def flatten_cols(cols):
        flat_cols = []
        for col in cols:
            parts = [str(c).strip() for c in col if str(c).lower() != 'nan' and str(c).strip() != '']
            flat_cols.append(' '.join(parts))
        return flat_cols

    df.columns = flatten_cols(df.columns)

    col_map = {}
    for col in df.columns:
        c = col.lower()
        if 'course code' in c or 'subcode' in c or c.strip() == 'code':
            col_map['Course Code'] = col
        elif 'course' in c or 'title' in c or 'subject' in c:
            col_map['Course Title'] = col
        elif re.search(r'\b(t)\b', c):
            col_map['T'] = col
        elif re.search(r'\b(tu)\b', c):
            col_map['Tu'] = col
        elif re.search(r'\b(p)\b', c):
            col_map['P'] = col
        elif 'credit' in c:
            col_map['Credits'] = col

    for key in ['Course Code', 'Course Title', 'T', 'Tu', 'P', 'Credits']:
        if key not in col_map:
            df[key] = None
            col_map[key] = key

    def clean_course_name(name):
        name = str(name).strip()
        name = re.sub(r'(Core|Practical|Elective|Enrichment|HSM|IDC|AECC)[\s\-]*\d*:? *', '', name, flags=re.I)
        name = re.sub(r'DSE\s*-?\s*\d+\s*', '', name, flags=re.I)
        name = re.sub(r'\([^)]*\)', '', name)
        name = re.sub(r':', '', name)
        name = re.sub(r'\s+', ' ', name).strip()
        return name

    def clean_hours(val):
        if pd.isna(val):
            return '-'
        val = str(val).strip()
        if val.isdigit():
            return int(val)
        if val == '-':
            return val
        m = re.search(r'\d+', val)
        return int(m.group()) if m else '-'

    def clean_credits(val):
        if pd.isna(val):
            return '-'
        val = str(val).strip()
        try:
            return int(float(val))
        except:
            m = re.search(r'\d+', val)
            return int(m.group()) if m else '-'

    def parse_int(value):
        if value == "-" or value is None:
            return 0
        return int(value)

    df[col_map['Course Code']] = df[col_map['Course Code']].astype(str).str.replace('\n', ' ', regex=False)
    df[col_map['Course Title']] = df[col_map['Course Title']].astype(str).str.replace('\n', ' ', regex=False)

    pattern = r'^\s*([0-9]{2}[A-Za-z]+\d+\s*(/\s*[0-9]{2}[A-Za-z]+\d+\s*)*)$'
    filtered = df[df[col_map['Course Code']].astype(str).str.match(pattern, na=False)]

    if filtered.empty:
        filtered = df[df[col_map['Course Code']].astype(str).str.contains(r'[0-9]{2}[A-Za-z]+\d+', na=False)]

    rows = []
    for _, row in filtered.iterrows():
        codes = [c.strip() for c in str(row[col_map['Course Code']]).split('/')]
        cleaned_titles_str = clean_course_name(str(row[col_map['Course Title']]))
        titles = [t.strip() for t in cleaned_titles_str.split('/')]

        for i, code in enumerate(codes):
            title = titles[i] if i < len(titles) else titles[-1]
            rows.append({
                'course_code': code,
                'course_name': title,
                't_hrs': parse_int(clean_hours(row[col_map['T']])),
                'tu_hrs': parse_int(clean_hours(row[col_map['Tu']])),
                'p_hrs': parse_int(clean_hours(row[col_map['P']])),
                'credits': parse_int(clean_credits(row[col_map['Credits']]))
            })

    result_df = pd.DataFrame(rows)
    result_df = result_df[~((result_df['t_hrs'] == 0) & (result_df['tu_hrs'] == 0) & (result_df['p_hrs'] == 0))]

    return result_df.to_dict(orient="records")
