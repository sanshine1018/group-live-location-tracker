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

from unicodedata import name

import streamlit as st
from streamlit_geolocation import streamlit_geolocation
from streamlit_folium import st_folium
import folium
from datetime import datetime
from supabase import create_client, Client
import secrets
import uuid
import math

###############################################################################
# Database helpers
###############################################################################

DB_PATH = "group_tracker.db"

#### marker color ####
COLORS = ["red", "blue", "green", "purple", "orange", "darkred", "cadetblue"]

@st.cache_resource
def get_supabase_client():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = get_supabase_client()

def get_user_color(user_id):
    return COLORS[user_id % len(COLORS)]

#### distance calculation ####

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )

    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))



def get_or_create_group(group_name: str)-> str:
    response = supabase.table("groups").select("id").eq("name", group_name).execute()
    if response.data:
        return response.data[0]["id"]
    group_id = secrets.token_hex(4)

    supabase.table("groups").insert({"id": group_id, "name": group_name}).execute()
    return group_id

def register_user(user_name: str, group_id: str) -> int:
    result = (
        supabase.table("users")
        .select("id")
        .eq("name", user_name)
        .eq("group_id", group_id)
        .execute()
    )

    if result.data:
        return result.data[0]["id"]

    insert_result = supabase.table("users").insert({
        "name": user_name,
        "group_id": group_id,
        "color": None
    }).execute()

    user_id = insert_result.data[0]["id"]
    color = get_user_color(user_id)

    supabase.table("users").update({
        "color": color
    }).eq("id", user_id).execute()

    return user_id


def update_position(user_id: int, latitude: float, longitude: float):
    supabase.table("positions").upsert({
        "user_id": user_id,
        "latitude": latitude,
        "longitude": longitude,
        "timestamp": datetime.utcnow().isoformat()
    }).execute()


def get_group_positions(group_id: str):
    result = (
        supabase.table("users")
        .select("id, name, color, positions(latitude, longitude, timestamp)")
        .eq("group_id", group_id)
        .execute()
    )

    return result.data


def set_destination(group_id: str, name: str, latitude: float, longitude: float):
    supabase.table("destinations").upsert({
        "group_id": group_id,
        "name": name,
        "latitude": latitude,
        "longitude": longitude
    }).execute()


def get_destination(group_id: str):
    result = (
        supabase.table("destinations")
        .select("*")
        .eq("group_id", group_id)
        .execute()
    )

    return result.data[0] if result.data else None





###############################################################################
# Streamlit user interface
###############################################################################

def main():
    """Main entry point for the Streamlit app."""

    st.set_page_config(
        page_title="Group Live Location Tracker",
        layout="wide"
    )

    st.title("🚶 Group Live Location Tracker")

    # =========================
    # JOIN / CREATE GROUP
    # =========================

    if "user_id" not in st.session_state or "group_id" not in st.session_state:

        st.subheader("Join or create a group")

        user_name = st.text_input(
            "Your display name",
            max_chars=50
        )

        group_name = st.text_input(
            "Group name",
            help="Enter a group name to create or join"
        )

        if st.button(
            "Join/Create Group",
            disabled=not user_name or not group_name
        ):

            group_id = get_or_create_group(group_name)

            user_id = register_user(
                user_name,
                group_id
            )

            st.session_state.user_id = user_id
            st.session_state.group_id = group_id
            st.session_state.user_name = user_name

            st.success(
                f"Welcome, {user_name}! "
                f"You joined group '{group_name}'"
            )

            st.rerun()

    # =========================
    # MAIN APP
    # =========================

    if "user_id" in st.session_state and "group_id" in st.session_state:

        group_id = st.session_state.group_id
        user_id = st.session_state.user_id
        user_name = st.session_state.user_name

        st.write(f"### Logged in as {user_name}")
        st.write(f"**Group ID:** `{group_id}`")

        # =========================
        # LOCATION UPDATE
        # =========================

        st.markdown("### Share your location")

        location = streamlit_geolocation()

        if location and location.get("latitude") is not None:

            lat = location["latitude"]
            lon = location["longitude"]

            update_position(
                user_id,
                lat,
                lon
            )

            st.success(
                f"Location updated: "
                f"{lat:.6f}, {lon:.6f}"
            )

        else:

            st.info(
                "Click 'Get my location' above."
            )

        # =========================
        # GET GROUP POSITIONS
        # =========================

        positions = get_group_positions(group_id)

        # =========================
        # CALCULATE MAP CENTER
        # =========================

        valid_positions = []

        for user in positions:

            pos = user.get("positions")

            if (
                pos
                and pos.get("latitude") is not None
                and pos.get("longitude") is not None
            ):

                valid_positions.append(
                    (
                        pos["latitude"],
                        pos["longitude"]
                    )
                )

        if valid_positions:

            avg_lat = (
                sum(p[0] for p in valid_positions)
                / len(valid_positions)
            )

            avg_lon = (
                sum(p[1] for p in valid_positions)
                / len(valid_positions)
            )

        else:

            avg_lat = 23.8070
            avg_lon = 90.4210

        # =========================
        # DESTINATION
        # =========================

        st.markdown("### Destination")

        destination_name = st.text_input(
            "Destination name"
        )

        dest_lat = st.number_input(
            "Destination latitude",
            value=23.8070,
            format="%.6f"
        )

        dest_lon = st.number_input(
            "Destination longitude",
            value=90.4210,
            format="%.6f"
        )

        if st.button("Set Destination"):

            set_destination(
                group_id,
                destination_name,
                dest_lat,
                dest_lon
            )

            st.success("Destination updated")

        destination = get_destination(group_id)

        # =========================
        # CREATE MAP
        # =========================

        m = folium.Map(
            location=[avg_lat, avg_lon],
            zoom_start=14
        )

        # =========================
        # DESTINATION MARKER
        # =========================

        if destination:

            folium.Marker(
                [
                    destination["latitude"],
                    destination["longitude"]
                ],
                popup=f"Destination: {destination['name']}",
                tooltip="Destination",
                icon=folium.Icon(
                    color="red",
                    icon="flag"
                )
            ).add_to(m)

        # =========================
        # USER MARKERS
        # =========================

        for user in positions:

            pos = user.get("positions")

            if not pos:
                continue

            latitude = pos.get("latitude")
            longitude = pos.get("longitude")
            ts = pos.get("timestamp")

            if latitude is None or longitude is None:
                continue

            name = user["name"]
            color = user.get("color") or "blue"

            pos = user.get("positions")
            timestamp = pos.get("timestamp") if pos else None

            if timestamp:
                try:
                    last_seen = datetime.fromisoformat(timestamp)
                except:
                    last_seen = datetime.strptime(
                    timestamp.split(".")[0],
                    "%Y-%m-%dT%H:%M:%S"
                    )
            else:
                last_seen = "Unknown"

            popup_text = f"""
            <b>{name}</b><br>
            Last seen: {last_seen}
            """
            
            # =========================
            # ETA
            # =========================

            if destination:

                distance_km = haversine(
                    latitude,
                    longitude,
                    destination["latitude"],
                    destination["longitude"]
                )

                eta_min = (
                    distance_km / 5
                ) * 60

                popup_text += f"""
                <br>Distance: {distance_km:.2f} km
                <br>ETA walking: {eta_min:.0f} min
                """

            folium.Marker(
                [latitude, longitude],
                popup=popup_text,
                tooltip=name,
                icon=folium.Icon(
                    color=color,
                    icon="user"
                )
            ).add_to(m)

        # =========================
        # SHOW MAP
        # =========================

        st.write("### Group Members' Locations")

        st_folium(
            m,
            width=1200,
            height=700
        )

        # =========================
        # MEMBER TABLE
        # =========================

        if positions:

            st.write("### Member List")

            table_data = []

            for user in positions:

                pos = user.get("positions")

                latitude = (
                    pos.get("latitude")
                    if pos else None
                )

                longitude = (
                    pos.get("longitude")
                    if pos else None
                )

                ts = (
                    pos.get("timestamp")
                    if pos else None
                )

                table_data.append({
                    "Name": user["name"],
                    "Latitude": (
                        f"{latitude:.6f}"
                        if latitude else "–"
                    ),
                    "Longitude": (
                        f"{longitude:.6f}"
                        if longitude else "–"
                    ),
                    "Last update": (
                        ts.replace("T", " ")
                        if ts else "–"
                    ),
                })

            st.table(table_data)


if __name__ == "__main__":
    main()