import pandas as pd
import sqlite3
import db

def parse_menge(val):
    """Converts German float string like '8,00' or float/int to integer >= 1."""
    if pd.isna(val) or val == '':
        return 1
    val_str = str(val).replace(',', '.').strip()
    try:
        qty = int(float(val_str))
        return max(1, qty)  # Ensure quantity is at least 1
    except ValueError:
        return 1

def import_csv_to_sqlite(file_path: str):
    db.init_db()

    # Load CSV with UTF-8 BOM encoding
    df = pd.read_csv(file_path, encoding='utf-8-sig')

    # Clean header names (strip spaces)
    df.columns = [str(col).strip() for col in df.columns]
    df = df.fillna('')

    print(f"🔍 Loaded Columns: {list(df.columns)}")

    conn = db.get_connection()
    cursor = conn.cursor()

    # Clear existing database records
    cursor.execute("DELETE FROM bookings;")
    cursor.execute("DELETE FROM items;")
    cursor.execute("DELETE FROM articles;")
    print("🧹 Cleared old inventory and bookings from database.")

    imported_count = 0

    for idx, row in df.iterrows():
        anzeigename = str(row.get('Anzeigename', '')).strip()
        menge = parse_menge(row.get('Aktuelle_Menge', 1))
        dok_filter = str(row.get('Dokumentfilter', '')).strip()
        ort = str(row.get('Lagerplatz', '')).strip().lstrip('- ').strip()

        # Skip empty rows
        if not anzeigename or anzeigename == 'nan':
            continue

        # Extract Category/Geräteart from prefix (e.g. "11-Tischleuchten")
        gerateart = dok_filter
        if "-" in anzeigename and not anzeigename.startswith("-"):
            gerateart = anzeigename.split("-")[0].strip()

        # Extract Manufacturer inside parentheses if available (e.g. "Eglo", "tomons")
        hersteller = "Unbekannt"
        if "(" in anzeigename and ")" in anzeigename:
            details = anzeigename.split("(")[1].split(")")[0]
            parts = details.split("-")
            if len(parts) >= 2:
                hersteller = parts[-1].strip()

        # 1. Insert Article Entry
        cursor.execute("""
            INSERT INTO articles (title, gerateart, hersteller)
            VALUES (?, ?, ?)
        """, (anzeigename, gerateart, hersteller))
        article_id = cursor.lastrowid

        # 2. Insert Physical Item Units
        for i in range(1, menge + 1):
            serial_number = f"INV-{article_id:03d}-{i:02d}"
            cursor.execute("""
                INSERT OR IGNORE INTO items (article_id, serial_number, ort, status)
                VALUES (?, ?, ?, 'available')
            """, (article_id, serial_number, ort))
            imported_count += 1

    conn.commit()
    conn.close()
    print(f"✅ Successfully imported {imported_count} units across new articles into library.db!")

if __name__ == "__main__":
    import_csv_to_sqlite('Data_clean.csv')