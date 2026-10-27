import streamlit as st
from datetime import datetime, date, time, timedelta
import db

from apscheduler.schedulers.background import BackgroundScheduler
from reminder_service import check_and_send_reminders

# --- BACKGROUND SCHEDULER ---
@st.cache_resource
def start_reminder_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_and_send_reminders, 'interval', minutes=5)
    scheduler.start()

start_reminder_scheduler()

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Ausleihe von Ausrüstung der Schulbibliothek",
    page_icon="📚",
    layout="wide"
)

st.title("📚 System zur Ausleihe von Rudolf Steiner-Schule 📚")
st.caption("Reservieren Sie Schulausrüstung für einige Stunden oder mehrere Tage.")

# Initialize database tables on app load
db.init_db()

# --- SIDEBAR: CATALOG BROWSING ---
st.sidebar.header("Ausrüstungskatalog")
articles = db.get_all_articles()

if not articles:
    st.sidebar.warning("No articles found in database. Please run import_inventory.py first.")
    st.stop()

# Build dropdown mapping display title -> article_id
article_options = {
    f"{a['title']} ({a['hersteller'] or 'Generic'})": a["id"] 
    for a in articles
}
selected_option = st.sidebar.selectbox("Ausrüstung auswählen", list(article_options.keys()))
selected_article_id = article_options[selected_option]

# Find selected article details
selected_article = next(a for a in articles if a["id"] == selected_article_id)

st.sidebar.info(
    f"**Kategorie:** {selected_article['gerateart'] or 'General'}\n\n"
    f"**Hersteller:** {selected_article['hersteller'] or 'N/A'}\n\n"
    f"**Gesamtzahl der Einheiten:** {selected_article['total_units']}"
)



# --- MAIN SECTION: RESERVATION SELECTOR ---
st.header(f"Reservieren: {selected_article['title']}")

rental_type = st.radio(
    "Art der Mietdauer auswählen:",
    ["⏱️ Stundenweise (einige Stunden)", "📅 Mehrtägig (ein oder mehrere Tage)"],
    horizontal=True
)

st.divider()

# --- DATETIME PICKER LOGIC ---
if "Stundenweise" in rental_type:
    col1, col2, col3 = st.columns(3)
    with col1:
        selected_date = st.date_input("Datum", min_value=date.today())
    with col2:
        start_time_input = st.time_input("Startzeit", value=time(9, 0))
    with col3:
        end_time_input = st.time_input("Endzeit", value=time(12, 0))

    start_datetime = datetime.combine(selected_date, start_time_input)
    end_datetime = datetime.combine(selected_date, end_time_input)

else:  # Multi-Day Rental
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Startdatum", min_value=date.today())
    with col2:
        end_date = st.date_input("Enddatum (Rückgabetag)", min_value=start_date + timedelta(days=1))

    # Default pickup at 08:00 AM on start date and return at 05:00 PM (17:00) on end date
    start_datetime = datetime.combine(start_date, time(8, 0))
    end_datetime = datetime.combine(end_date, time(17, 0))

start_str = start_datetime.strftime("%Y-%m-%d %H:%M:%S")
end_str = end_datetime.strftime("%Y-%m-%d %H:%M:%S")

# Time validation
if end_datetime <= start_datetime:
    st.error("⚠️ Zeit/Datum der Rückgabe müssen nach der Zeit/dem Datum der Abholung liegen.")
    st.stop()

# # --- REAL-TIME AVAILABILITY QUERY ---
# available_item = db.get_available_item_for_article(selected_article_id, start_str, end_str)

# if available_item:
#     st.success(
#         f"✅ **Einheit verfügbar** für Reservierungen ab `{start_str}` bis `{end_str}`."
#     )
# else:
#     st.error(
#         f"❌ **Keine Einheiten verfügbar** für den ausgewählten Zeitraum (`{start_str}` bis `{end_str}`). "
#         f"Alle Einheiten sind in diesem Zeitraum reserviert."
#     )

# # --- BOOKING FORM ---
# if available_item:
#     st.subheader("Checkout-Formular")
    
#     with st.form("checkout_form"):
#         user_name = st.text_input("Name des Schülers / Lehrers", placeholder="z. B. Günter Bürger")
#         user_email = st.text_input("Schul-E-Mail", placeholder="z. B. g.bürger@waldorfschule-nuernberg.edu")
        
#         submitted = st.form_submit_button("Reservierung bestätigen")
        
#         if submitted:
#             if not user_name or not user_email:
#                 st.warning("Bitte geben Sie sowohl Ihren Namen als auch Ihre E-Mail-Adresse ein.")
#             elif "@" not in user_email:
#                 st.warning("Bitte geben Sie eine gültige Schul-E-Mail-Adresse ein.")
#             else:
#                 assigned_item_id = available_item["id"]
#                 serial = available_item["serial_number"]
#                 location = available_item["ort"] or "Main Desk"

#                 # Save booking in SQLite
#                 db.create_booking(
#                     item_id=assigned_item_id,
#                     user_name=user_name,
#                     user_email=user_email,
#                     start_time=start_str,
#                     end_time=end_str
#                 )

#                 st.balloons()
#                 st.success(
#                     f"🎉 **Reservierung bestätigt!**\n\n"
#                     f"- **Artikel:** {selected_article['title']}\n"
#                     f"- **Inventarnummer:** `{serial}`\n"
#                     f"- **Abholort:** {location}\n"
#                     f"- **Mieter*in:** {user_name} ({user_email})\n"
#                     f"- **Zeitfenster:** {start_str} to {end_str}"
#                 )

# --- REAL-TIME AVAILABILITY & QUANTITY SELECTION ---
available_items = db.get_available_items_for_article(selected_article_id, start_str, end_str)
total_units = selected_article['total_units'] or len(available_items)
available_count = len(available_items)

# Display real-time availability status badge
if available_count > 0:
    st.success(
        f"✅ **Verfügbar:** **{available_count} von {total_units} Einheiten** "
        f"im Zeitraum `{start_str}` bis `{end_str}`."
    )
else:
    st.error(
        f"❌ **Keine Einheiten verfügbar** im ausgewählten Zeitraum (`{start_str}` bis `{end_str}`). "
        f"Alle {total_units} Einheiten sind in diesem Zeitraum bereits ausgebucht."
    )

# --- BOOKING FORM WITH DYNAMIC UNIQUE KEY ---
if available_count > 0:
    st.subheader("Checkout-Formular")

    with st.form(key=f"checkout_form_{selected_article_id}"):
        col_qty, col_blank = st.columns([2, 3])
        with col_qty:
            requested_qty = st.number_input(
                "Anzahl der zu mietenden Einheiten:",
                min_value=1,
                max_value=available_count,
                value=1,
                step=1,
                help=f"Sie können maximal {available_count} Einheit(en) für diesen Zeitraum auswählen."
            )

        user_name = st.text_input("Name des Schülers / Lehrers", placeholder="z. B. Günter Bürger")
        user_email = st.text_input("Schul-E-Mail", placeholder="z. B. g.bürger@waldorfschule-nuernberg.edu")

        submitted = st.form_submit_button("Reservierung bestätigen")

        if submitted:
            if not user_name or not user_email:
                st.warning("Bitte geben Sie sowohl Ihren Namen als auch Ihre E-Mail-Adresse ein.")
            elif "@" not in user_email:
                st.warning("Bitte geben Sie eine gültige Schul-E-Mail-Adresse ein.")
            else:
                # Select the requested number of physical items
                selected_items = available_items[:requested_qty]
                selected_item_ids = [item["id"] for item in selected_items]
                serials = ", ".join([f"`{item['serial_number']}`" for item in selected_items])
                location = selected_items[0]["ort"] or "Haupttresen"

                # Save all selected units in SQLite
                db.create_multi_booking(
                    item_ids=selected_item_ids,
                    user_name=user_name,
                    user_email=user_email,
                    start_time=start_str,
                    end_time=end_str
                )

                st.balloons()
                st.success(
                    f"🎉 **Reservierung von {requested_qty} Einheit(en) erfolgreich!**\n\n"
                    f"- **Artikel:** {selected_article['title']}\n"
                    f"- **Anzahl:** {requested_qty} Stück\n"
                    f"- **Inventarnummer(n):** {serials}\n"
                    f"- **Abholort:** {location}\n"
                    f"- **Mieter*in:** {user_name} ({user_email})\n"
                    f"- **Zeitfenster:** {start_str} bis {end_str}"
                )

# --- ADMIN OVERVIEW & RETURN MANAGEMENT ---
st.divider()
with st.expander("📋 Admin-Dashboard: Vermietungsverwaltung & Historie", expanded=False):
    tab1, tab2 = st.tabs(["🔄 Aktiv-Verleih", "📜 Verlauf der Rückgaben"])

    # --- TAB 1: ACTIVE RENTALS ---
    with tab1:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                b.id AS booking_id,
                a.title AS item_title,
                i.serial_number,
                i.ort,
                b.user_name,
                b.user_email,
                b.start_time,
                b.end_time,
                b.status
            FROM bookings b
            JOIN items i ON b.item_id = i.id
            JOIN articles a ON i.article_id = a.id
            WHERE b.status = 'checked_out'
            ORDER BY b.start_time ASC
        """)
        active_bookings = cursor.fetchall()
        conn.close()

        if active_bookings:
            st.write(f"**Aktuell aktive Mietobjekte ({len(active_bookings)}):**")
            
            for booking in active_bookings:
                b_id = booking["booking_id"]
                title = booking["item_title"]
                serial = booking["serial_number"]
                user = booking["user_name"]
                end_t = booking["end_time"]
                location = booking["ort"] or "Main Desk"
                
                col_info, col_user, col_due, col_action = st.columns([3, 2, 3, 2])
                
                with col_info:
                    st.markdown(f"**{title}** (`{serial}`)\n\n📍 *{location}*")
                with col_user:
                    st.markdown(f"👤 {user}")
                with col_due:
                    st.markdown(f"⏱️ Fällig: `{end_t}`")
                with col_action:
                    if st.button("Mark ist zurückgekehrt", key=f"return_btn_{b_id}"):
                        db.return_booking(b_id)
                        st.toast(f"✅ Artikel '{serial}' erfolgreich zurückgegeben!", icon="🎉")
                        st.rerun()
                        
                st.divider()
        else:
            st.info("🎉 Momentan keine aktiven Ausleihen. Alle Artikel befinden sich in der Bibliothek!")



    # --- TAB 2: RETURNED HISTORY LOG ---
    with tab2:
        returned_bookings = db.get_returned_bookings()
        
        if returned_bookings:
            st.write(f"**Früher zurückgegebene Artikel ({len(returned_bookings)}):**")
            
            history_data = [
                {
                    "Buchungsnummer": r["booking_id"],
                    "Artikel": r["item_title"],
                    "Inventarnummer": r["serial_number"],
                    "Name des Mieters": r["user_name"],
                    "Email": r["user_email"],
                    "Startzeit": r["start_time"],
                    "Endzeit": r["end_time"],
                    "Status": "✅ Zurückgegeben"
                }
                for r in returned_bookings
            ]
            
            st.dataframe(
                history_data, 
                width='stretch', 
                #use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Bisher wurden keine Rücksendungen verzeichnet.")

# --- ADMIN TAB: ACTIVE RENTALS MANAGEMENT ---
st.header("📋 Dashboard für aktive Vermietungen")

active_rentals = db.get_active_bookings()

if not active_rentals:
    st.info("ℹ️Derzeit sind keine Artikel ausgeliehen.")
else:
    # 1. Search Bar and Category Filter Controls
    col_search, col_filter = st.columns([3, 2])
    
    with col_search:
        search_term = st.text_input(
            "🔍 Aktive Mietangebote durchsuchen:", 
            placeholder="Name des Mieters, E-Mail, Artikelbezeichnung oder Seriennummer eingeben..."
        )
        
    with col_filter:
        # Extract unique equipment types dynamically
        categories = sorted(list(set([r["gerateart"] for r in active_rentals if r["gerateart"]])))
        selected_category = st.selectbox("Nach Kategorie filtern:", ["All Categories"] + categories)

    # 2. Filtering Logic
    filtered_rentals = active_rentals

    if search_term:
        q = search_term.lower()
        filtered_rentals = [
            r for r in filtered_rentals
            if q in r["user_name"].lower()
            or q in r["user_email"].lower()
            or q in r["item_title"].lower()
            or q in r["serial_number"].lower()
        ]

    if selected_category != "All Categories":
        filtered_rentals = [r for r in filtered_rentals if r["gerateart"] == selected_category]

    # 3. Display Status Count
    st.caption(f"Anzeige {len(filtered_rentals)} von {len(active_rentals)} Aktive Mietverhältnisse")

    # 4. Render Active Rentals
    if not filtered_rentals:
        st.warning("Es gibt keine aktiven Mietangebote, die Ihren Suchkriterien entsprechen.")
    else:
        for rental in filtered_rentals:
            with st.expander(f"📦 {rental['item_title']} — Vermietet von: {rental['user_name']} ({rental['serial_number']})"):
                c1, c2, c3 = st.columns([3, 3, 2])
                
                with c1:
                    st.write(f"**Mieter*in:** {rental['user_name']}")
                    st.write(f"**Email:** {rental['user_email']}")
                    st.write(f"**Kategorie:** {rental['gerateart'] or 'General'}")

                with c2:
                    st.write(f"**Serial:** `{rental['serial_number']}`")
                    st.write(f"**Ort:** {rental['ort'] or 'N/A'}")
                    st.write(f"**Zur rechten Zeit:** {rental['end_time']}")

                with c3:
                    # Action button to check back in
                    if st.button("📥 Artikel zurückgeben", key=f"return_{rental['booking_id']}", type="primary"):
                        db.return_booking(rental['booking_id'])
                        st.success(f"Zurückgegeben {rental['item_title']} ({rental['serial_number']})!")
                        st.rerun()