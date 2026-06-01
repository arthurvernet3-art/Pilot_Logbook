# Pilot Logbook Streamlit App

This is a phone-friendly Streamlit prototype for a private pilot electronic logbook.

## What it does

- Add flights with aircraft, route, hours, landings, and remarks.
- Save aircraft profiles the first time you log an aircraft, then pick them from recent aircraft.
- Attach an aircraft picture to a saved aircraft profile.
- Pick recent departure/arrival airports or search the full France/Switzerland airport database.
- Use the in-flight tab to log off-blocks, takeoff, landings, and on-blocks with UTC times rounded to the nearest 5 minutes.
- Plan intermediate stops or touch-and-goes, then log each planned event with its own quick UTC button in flight.
- Save multi-airport routes as one logbook row per sector.
- Delete selected logbook entries from the Logbook tab.
- Add aircraft directly from the Data page.
- See aircraft photos next to aircraft cards in the Data page.
- Navigate with a compact menu instead of a permanently visible tab bar.
- Use the Home page for totals, status, map, and recent flight cards.
- Review logbook entries, deadlines, aircraft, and recent flights as clean cards instead of spreadsheet-style tables.
- Aviation-code fields such as registrations, aircraft types/classes, and airport criteria are normalized to uppercase.
- Build routes as a chain of airports: Airport 1, Airport 2, then add more airports as needed.
- Enter UTC times for departure, intermediate, and arrival airports.
- Set a landing count for each intermediate stop or touch-and-go, and let the app set the minimum total landings automatically.
- Choose whether the flight time is logged as PIC or DC instead of showing all time buckets at once.
- Switch the main interface between English and French from the menu.
- Check passenger-carrying currency, including custom local criteria such as a shorter lookback at a specific aerodrome.
- Show totals for flights, hours, PIC time, and landings.
- Draw flown routes on a map.
- Track medical, licence, rating, insurance, and currency deadlines.
- Warn when a deadline is inside its reminder window.
- Download and restore a JSON backup.

Flight times are entered as hours and minutes, then stored internally as minutes.

The included airport database is generated from the open OurAirports data and filtered to France and Switzerland airport entries. Treat it as a convenience database, not an official AIP source.

## Run it

```bash
pip install -r requirements.txt
streamlit run app.py --server.address 0.0.0.0
```

Open the local Streamlit URL on your computer. To use it on your phone, make sure the phone is on the same Wi-Fi network and open the network URL shown by Streamlit.

## Phone use

For a real phone app feel, deploy it to Streamlit Community Cloud, a small VPS, or a private home server. Then add the site to your phone's home screen.

Push notifications are not built into plain Streamlit. For real alerts, the next step would be email reminders, calendar export, or integration with iOS/Google reminders.

## Structure

- `app.py` is the Streamlit front end and page layout.
- `storage.py` loads, saves, migrates data, and stores aircraft images.
- `airports.py` loads and labels the airport database.
- `rules.py` contains time formatting, deadline status, map rows, and currency calculations.
- `ui_components.py` contains reusable aircraft, airport, and duration controls.
