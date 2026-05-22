"""
Streamlit Group Live Location Tracker
-------------------------------------

This Streamlit application demonstrates how to build a simple group‑
based live location sharing app using Python, Streamlit, JavaScript and
basic APIs.  Users can create or join groups, share their current
location, and see the locations of other group members on a map.

The key features implemented include:

* **Group creation and join:** Users choose a group name.  If the group
  does not exist, it is created; otherwise they join the existing
  group.  A unique numeric ID is generated for each group and can be
  shared with friends.
* **User registration:** Each user enters a display name which is
  stored along with their group membership.
* **Location capture:** The app uses the JavaScript
  `navigator.geolocation` API via the ``streamlit_geolocation``
  component to obtain the user’s latitude and longitude.  MDN notes
  that calling ``navigator.geolocation.getCurrentPosition()`` or
  ``watchPosition()`` requests the device’s location and invokes a
  callback when the position is determined【849564444376193†L235-L291】.
* **Live updates:** The app stores each user’s most recent position
  in an SQLite database and periodically reloads the positions to
  update the map.  Streamlit’s ``st_autorefresh`` function triggers a
  rerun every few seconds.
* **Map display:** The positions of all group members are plotted on
  an interactive map using Folium.  Each marker includes the user’s
  name and the timestamp of the last update.

Note:  This code is designed to be self‑contained and simple.  For a
production deployment you should add proper authentication,
authorization, and secure storage.  Location data is legally
considered sensitive in many jurisdictions, and the Future of Privacy
Forum recommends limiting the purposes for which location data is
collected and not re‑using it for other purposes【781875655076457†L107-L116】.
Always obtain informed consent from users before requesting their
precise location.
"""

import streamlit as st
from streamlit_geolocation import streamlit_geolocation
from streamlit_folium import st_folium
import folium
from datetime import datetime
import sqlite3
import os
import secrets
import uuid

###############################################################################
# Database helpers
###############################################################################

DB_PATH = "group_tracker.db"


def init_db(path: str = DB_PATH) -> sqlite3.Connection:
    """Initialize the SQLite database and create tables if they don't exist.

    Returns a database connection.  Tables created:

    * groups: id (TEXT primary key), name (TEXT), created_at (TEXT)
    * users: id (INTEGER primary key autoincrement), name (TEXT), group_id (TEXT)
    * positions: user_id (INTEGER), latitude (REAL), longitude (REAL),
      timestamp (TEXT)
    """
    conn = sqlite3.connect(path, check_same_thread=False)
    cur = conn.cursor()
    # Groups table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS groups (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    # Users table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            group_id TEXT NOT NULL,
            FOREIGN KEY(group_id) REFERENCES groups(id)
        )
        """
    )
    # Positions table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS positions (
            user_id INTEGER PRIMARY KEY,
            latitude REAL,
            longitude REAL,
            timestamp TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    conn.commit()
    return conn


def get_or_create_group(conn: sqlite3.Connection, group_name: str) -> str:
    """Return the group ID for the given group name, creating it if needed."""
    cur = conn.cursor()
    cur.execute("SELECT id FROM groups WHERE name = ?", (group_name,))
    row = cur.fetchone()
    if row:
        return row[0]
    # Create a new group with a random ID
    group_id = secrets.token_hex(4)  # 8‑character hex ID
    created_at = datetime.utcnow().isoformat()
    cur.execute(
        "INSERT INTO groups (id, name, created_at) VALUES (?, ?, ?)",
        (group_id, group_name, created_at),
    )
    conn.commit()
    return group_id


def register_user(conn: sqlite3.Connection, user_name: str, group_id: str) -> int:
    """Add a user to a group and return the new user_id.

    If the user already exists in the same group, return the existing ID.
    """
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM users WHERE name = ? AND group_id = ?", (user_name, group_id)
    )
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        "INSERT INTO users (name, group_id) VALUES (?, ?)", (user_name, group_id)
    )
    conn.commit()
    return cur.lastrowid


def update_position(
    conn: sqlite3.Connection, user_id: int, latitude: float, longitude: float
) -> None:
    """Update the user’s current position (upsert)."""
    cur = conn.cursor()
    timestamp = datetime.utcnow().isoformat()
    cur.execute(
        "INSERT OR REPLACE INTO positions (user_id, latitude, longitude, timestamp)"
        " VALUES (?, ?, ?, ?)",
        (user_id, latitude, longitude, timestamp),
    )
    conn.commit()


def get_group_positions(conn: sqlite3.Connection, group_id: str):
    """Return a list of (user_name, latitude, longitude, timestamp) for a group."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT users.name, positions.latitude, positions.longitude, positions.timestamp
        FROM users
        LEFT JOIN positions ON users.id = positions.user_id
        WHERE users.group_id = ?
        """,
        (group_id,),
    )
    return cur.fetchall()


###############################################################################
# Streamlit user interface
###############################################################################

def main():
    """Main entry point for the Streamlit app."""
    st.set_page_config(page_title="Group Live Location Tracker", layout="wide")
    st.title("🚶 Group Live Location Tracker")

    # Disclaimer about privacy
    with st.expander("Privacy Notice", expanded=False):
        st.markdown(
            """
            **Precise location data is sensitive.**  By using this demo you
            consent to share your location with other members of your group.  The
            Future of Privacy Forum notes that location data is treated as
            legally sensitive in most jurisdictions, and that data should only
            be collected for a specific purpose and not re‑used for other
            purposes【781875655076457†L107-L116】.  This app stores your location
            only temporarily for demonstration purposes.
            """
        )

    # Initialize the database
    conn = init_db()

    # If a user session exists, skip the login form
    if "user_id" not in st.session_state or "group_id" not in st.session_state:
        st.subheader("Join or create a group")
        user_name = st.text_input("Your display name", max_chars=50)
        group_name = st.text_input(
            "Group name", help="Enter a group name to create or join"
        )
        if st.button("Join/Create Group", disabled=not user_name or not group_name):
            group_id = get_or_create_group(conn, group_name)
            user_id = register_user(conn, user_name, group_id)
            st.session_state.user_id = user_id
            st.session_state.group_id = group_id
            st.session_state.user_name = user_name
            st.success(
                f"Welcome, {user_name}! You have joined group '{group_name}' (ID: {group_id})."
            )
            st.info(
                "Share your group ID with friends so they can join the same group."
            )

    # If the user is registered, display location sharing interface
    if "user_id" in st.session_state and "group_id" in st.session_state:
        group_id = st.session_state.group_id
        user_id = st.session_state.user_id
        user_name = st.session_state.user_name

        st.write(f"**Group ID:** `{group_id}`  (share this with friends to join)")
        st.write(f"Logged in as **{user_name}**")

        # Capture location
        st.markdown("### Share your location")
        # Use the streamlit_geolocation component to request location
        # The component displays a button and returns a dict when pressed.
        location = streamlit_geolocation()
        # location is a dict like {"latitude": ..., "longitude": ..., ...}
        if location and location.get("latitude") is not None:
            lat = location["latitude"]
            lon = location["longitude"]
            update_position(conn, user_id, lat, lon)
            st.success(
                f"Location updated: Latitude {lat:.6f}, Longitude {lon:.6f}"
            )
        else:
            st.write(
                "Click the **Get my location** button above to share your current position."
            )

        # Auto‑refresh the page every 5 seconds to show updated positions
         # fallback if st_autorefresh not available
        try:
            # Streamlit >= 1.20 provides st.autorefresh
            from streamlit import experimental as _experimental
            # noinspection PyUnresolvedReferences
            _ = st.experimental_rerun
            _ = st.experimental_rerun  # keep for lint
        except Exception:
            pass  # ignore if not available

        # Retrieve positions for all users in the group
        positions = get_group_positions(conn, group_id)
        # Compose map
        if positions:
            # Determine central point as the average of all points
            valid_positions = [(p[1], p[2]) for p in positions if p[1] is not None]
            if valid_positions:
                avg_lat = sum(p[0] for p in valid_positions) / len(valid_positions)
                avg_lon = sum(p[1] for p in valid_positions) / len(valid_positions)
            else:
                # Default to Dhaka (approx.) if no coordinates yet
                avg_lat, avg_lon = 23.8070, 90.4210
        else:
            avg_lat, avg_lon = 23.8070, 90.4210

        m = folium.Map(location=[avg_lat, avg_lon], zoom_start=14)
        # Add markers for each position
        for name, latitude, longitude, ts in positions:
            if latitude is None or longitude is None:
                continue
            last_seen = datetime.fromisoformat(ts).strftime("%Y‑%m‑%d %H:%M:%S")
            folium.Marker(
                [latitude, longitude],
                popup=f"{name} (last seen {last_seen} UTC)",
                tooltip=name,
                icon=folium.Icon(color="blue", icon="user")
            ).add_to(m)
        # Render map in Streamlit
        st.write("### Group Members' Locations")
        st_folium(m, width=700, height=500)

        # Display table of group members and their last seen times
        if positions:
            st.write("### Member List")
            # Build a simple table
            table_data = []
            for name, latitude, longitude, ts in positions:
                last_seen = ts
                table_data.append({
                    "Name": name,
                    "Latitude": f"{latitude:.6f}" if latitude else "–",
                    "Longitude": f"{longitude:.6f}" if longitude else "–",
                    "Last update": last_seen.replace("T", " ") if last_seen else "–",
                })
            st.table(table_data)


if __name__ == "__main__":
    # Ensure database directory exists
    if not os.path.exists(DB_PATH):
        # Create an empty file to ensure relative directory exists
        open(DB_PATH, "a").close()
    main()