import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from datetime import datetime
import math

# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="PRANARAKSHA AI",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================================================
# CUSTOM CSS
# =========================================================

st.markdown("""
<style>

.main {
    background-color: #ffffff;
}

.block-container {
    padding-top: 1.5rem;
}

.big-title {
    font-size: 42px;
    font-weight: 800;
    color: #202735;
    margin-bottom: 5px;
}

.subtitle {
    font-size: 20px;
    color: #707070;
    font-style: italic;
    margin-bottom: 20px;
}

.section-title {
    font-size: 27px;
    font-weight: 750;
    color: #202735;
    margin-top: 10px;
    margin-bottom: 10px;
}

.red-card {
    background: #ffe5e5;
    padding: 16px;
    border-radius: 10px;
    color: #9b1c1c;
    font-weight: 600;
}

.green-card {
    background: #e7f7ed;
    padding: 16px;
    border-radius: 10px;
    color: #176b3a;
    font-weight: 600;
}

.yellow-card {
    background: #fff7d6;
    padding: 16px;
    border-radius: 10px;
    color: #795900;
    font-weight: 600;
}

.info-card {
    background: #eef5ff;
    padding: 16px;
    border-radius: 10px;
    color: #174a7e;
    font-weight: 600;
}

</style>
""", unsafe_allow_html=True)


# =========================================================
# LIVE WEATHER
# =========================================================

@st.cache_data(ttl=300)
def get_live_weather(lat, lon):

    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": lat,
        "longitude": lon,
        "current": (
            "temperature_2m,"
            "relative_humidity_2m,"
            "precipitation,"
            "rain,"
            "weather_code,"
            "wind_speed_10m"
        ),
        "timezone": "auto"
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=15
        )

        response.raise_for_status()

        data = response.json()

        current = data.get("current", {})

        return {
            "temperature": current.get("temperature_2m", 0),
            "humidity": current.get("relative_humidity_2m", 0),
            "precipitation": current.get("precipitation", 0),
            "rain": current.get("rain", 0),
            "weather_code": current.get("weather_code", 0),
            "wind": current.get("wind_speed_10m", 0),
            "time": current.get("time", "Unavailable")
        }

    except Exception as e:

        return {
            "temperature": 0,
            "humidity": 0,
            "precipitation": 0,
            "rain": 0,
            "weather_code": 0,
            "wind": 0,
            "time": "Unavailable"
        }


# =========================================================
# LIVE ELEVATION -> REAL SLOPE
# (Open-Meteo Elevation API, free, no key required)
# =========================================================

@st.cache_data(ttl=3600)
def get_live_slope(lat, lon):
    """
    Samples elevation at the center point plus four points
    ~500m away (N/S/E/W) and derives an approximate slope
    in degrees. Replaces the old hardcoded CURRENT_SLOPE.
    """

    url = "https://api.open-meteo.com/v1/elevation"

    # ~500m offset in degrees latitude; longitude offset
    # adjusted for latitude to keep the distance roughly equal
    d_lat = 0.0045
    d_lon = 0.0045 / max(math.cos(math.radians(lat)), 0.1)

    sample_points = [
        (lat, lon),
        (lat + d_lat, lon),
        (lat - d_lat, lon),
        (lat, lon + d_lon),
        (lat, lon - d_lon),
    ]

    lats = ",".join(str(p[0]) for p in sample_points)
    lons = ",".join(str(p[1]) for p in sample_points)

    try:

        response = requests.get(
            url,
            params={"latitude": lats, "longitude": lons},
            timeout=15
        )

        response.raise_for_status()

        elevations = response.json().get("elevation", [])

        if len(elevations) < 5:
            return 10.0, elevations[:1] or [0]

        center = elevations[0]
        neighbours = elevations[1:]

        # Horizontal distance for each sample (~500m)
        distance_m = 500

        max_slope_deg = 0.0

        for elev in neighbours:

            rise = abs(elev - center)
            angle = math.degrees(math.atan2(rise, distance_m))
            max_slope_deg = max(max_slope_deg, angle)

        return round(max_slope_deg, 2), elevations

    except Exception:

        return 10.0, []


# =========================================================
# LIVE RIVER DISCHARGE / FLOOD RISK
# (Open-Meteo Flood API, free, no key required)
# =========================================================

@st.cache_data(ttl=1800)
def get_live_flood_data(lat, lon):
    """
    Pulls current daily river discharge (m3/s) for the nearest
    modeled river reach. Used as a real flood-risk signal
    instead of relying on rainfall alone.
    """

    url = "https://flood-api.open-meteo.com/v1/flood"

    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "river_discharge",
        "forecast_days": 1
    }

    try:

        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()

        data = response.json()
        daily = data.get("daily", {})
        discharge_values = daily.get("river_discharge", [])

        discharge = discharge_values[0] if discharge_values else None

        return {
            "discharge": discharge,
            "available": discharge is not None
        }

    except Exception:

        return {"discharge": None, "available": False}


# =========================================================
# LIVE EARTHQUAKE FEED
# (USGS Earthquake API, free, no key required)
# =========================================================

@st.cache_data(ttl=900)
def get_nearby_earthquakes(lat, lon, radius_km=300, min_magnitude=3.0):
    """
    Returns recent (last 7 days) earthquakes within radius_km
    of the selected location.
    """

    url = "https://earthquake.usgs.gov/fdsnws/event/1/query"

    params = {
        "format": "geojson",
        "latitude": lat,
        "longitude": lon,
        "maxradiuskm": radius_km,
        "minmagnitude": min_magnitude,
        "starttime": "now-7days",
        "orderby": "time"
    }

    try:

        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()

        features = response.json().get("features", [])

        quakes = []

        for f in features[:10]:

            props = f.get("properties", {})
            coords = f.get("geometry", {}).get("coordinates", [0, 0, 0])

            quakes.append({
                "place": props.get("place", "Unknown location"),
                "magnitude": props.get("mag", 0),
                "time": datetime.utcfromtimestamp(
                    props.get("time", 0) / 1000
                ).strftime("%Y-%m-%d %H:%M UTC"),
                "lon": coords[0],
                "lat": coords[1]
            })

        return quakes

    except Exception:

        return []


# =========================================================
# WEATHER DESCRIPTION
# =========================================================

def weather_description(code):

    code = int(code)

    descriptions = {

        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",

        45: "Fog",
        48: "Depositing rime fog",

        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",

        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",

        71: "Slight snowfall",
        73: "Moderate snowfall",
        75: "Heavy snowfall",

        80: "Slight rain showers",
        81: "Moderate rain showers",
        82: "Violent rain showers",

        95: "Thunderstorm",
        96: "Thunderstorm with hail",
        99: "Severe thunderstorm"
    }

    return descriptions.get(
        code,
        "Weather condition unavailable"
    )


# =========================================================
# RISK CALCULATION
# (now folds in real slope, flood discharge, quake activity)
# =========================================================

def calculate_risk(weather, slope, flood_discharge=None, quake_count=0):

    rainfall = float(weather["precipitation"])
    humidity = float(weather["humidity"])
    wind = float(weather["wind"])
    weather_code = int(weather["weather_code"])

    # Rainfall risk
    rainfall_risk = min(
        (rainfall / 50) * 100,
        100
    )

    # Slope risk (now from live elevation data)
    slope_risk = min(
        (slope / 45) * 100,
        100
    )

    # Humidity proxy
    soil_risk = humidity

    # Hazard score
    hazard = (
        rainfall_risk * 0.45 +
        slope_risk * 0.25 +
        soil_risk * 0.15
    )

    # Wind risk
    wind_risk = min(
        (wind / 60) * 100,
        100
    )

    # Flood/discharge risk (normalized against a high-flow reference)
    flood_risk = 0
    if flood_discharge:
        flood_risk = min((flood_discharge / 500) * 100, 100)

    # Thunderstorm bonus
    storm_bonus = 10 if weather_code in [95, 96, 99] else 0

    # Seismic bonus (recent nearby quakes M3.0+)
    quake_bonus = min(quake_count * 4, 15)

    # Final risk
    final_risk = (
        hazard * 0.70 +
        wind_risk * 0.10 +
        flood_risk * 0.10 +
        storm_bonus +
        quake_bonus
    )

    final_risk = min(
        max(final_risk, 0),
        100
    )

    # Classification
    if final_risk >= 70:

        level = "RED"

    elif final_risk >= 40:

        level = "YELLOW"

    else:

        level = "GREEN"

    return round(final_risk, 2), level


# =========================================================
# RISK COLOR
# =========================================================

def risk_color(level):

    if level == "RED":
        return "red"

    elif level == "YELLOW":
        return "orange"

    return "green"


# =========================================================
# TITLE
# =========================================================

st.markdown(
    '<div class="big-title">🛡️ PRANARAKSHA AI</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    'Carrying Capacity & Hazard Relocation Engine'
    '</div>',
    unsafe_allow_html=True
)

st.markdown(
    "**Disaster Risk & Relief Management Decision Support Portal**"
)

st.caption(
    "SIH26191 | Hazard Identification | Carrying Capacity | Relocation Support"
)


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.markdown("## ⚙️ Risk & Carrying Capacity Controls")

    st.markdown("### Risk Threshold")

    threshold = st.slider(
        "High-risk cutoff (%)",
        min_value=10,
        max_value=95,
        value=55,
        step=5
    )

    st.caption(
        f"Zones with risk ≥ {threshold}% "
        "will enter the evacuation queue."
    )

    st.markdown("---")

    st.markdown("## 💧 Carrying Capacity Standards")

    water_norm = st.number_input(
        "Water Norm (Liters/Person/Day)",
        min_value=50,
        max_value=300,
        value=135,
        step=5
    )

    land_norm = st.number_input(
        "Land Norm per Family (sq.m)",
        min_value=50,
        max_value=500,
        value=120,
        step=10
    )

    st.markdown("---")

    st.markdown("## 📡 Control Panel")

    sync = st.button(
        "🔄 Sync Live Data (Weather, Slope, Flood, Quakes)",
        use_container_width=True
    )

    if sync:

        st.cache_data.clear()

        st.success(
            "Live data refreshed!"
        )

        st.rerun()

    st.markdown("---")

    st.info(
        "🌦️ Live weather: Open-Meteo\n\n"
        "⛰️ Live slope: Open-Meteo Elevation API\n\n"
        "🌊 Live river discharge: Open-Meteo Flood API\n\n"
        "🌍 Live earthquakes: USGS (last 7 days)\n\n"
        "🗺️ Map: OpenStreetMap\n\n"
        "📍 GIS zones: Prototype records"
    )


# =========================================================
# LOCATION
# =========================================================

locations = {

    "Rajamahendravaram": {
        "lat": 17.0005,
        "lon": 81.8040
    },

    "Amalapuram": {
        "lat": 16.5787,
        "lon": 82.0061
    },

    "Visakhapatnam": {
        "lat": 17.6868,
        "lon": 83.2185
    },

    "Vijayawada": {
        "lat": 16.5062,
        "lon": 80.6480
    },

    "Guntur": {
        "lat": 16.3067,
        "lon": 80.4365
    },

    "Tirupati": {
        "lat": 13.6288,
        "lon": 79.4192
    },

    "Kurnool": {
        "lat": 15.8281,
        "lon": 78.0373
    },

    "Anantapur": {
        "lat": 14.6819,
        "lon": 77.6006
    },

    "Nellore": {
        "lat": 14.4426,
        "lon": 79.9865
    }
}


selected_location = st.selectbox(
    "📍 Select Monitoring Location",
    list(locations.keys())
)

LAT = locations[selected_location]["lat"]
LON = locations[selected_location]["lon"]


# =========================================================
# LIVE DATA PULLS
# =========================================================

weather = get_live_weather(LAT, LON)
live_slope, elevation_samples = get_live_slope(LAT, LON)
flood_data = get_live_flood_data(LAT, LON)
earthquakes = get_nearby_earthquakes(LAT, LON)


# =========================================================
# CURRENT RISK
# =========================================================

risk, risk_level = calculate_risk(
    weather,
    live_slope,
    flood_discharge=flood_data.get("discharge"),
    quake_count=len(earthquakes)
)


# =========================================================
# LIVE WEATHER HEADER
# =========================================================

st.markdown(
    "## 🌦️ Live Environmental Conditions"
)

c1, c2, c3, c4, c5 = st.columns(5)


with c1:

    st.metric(
        "Temperature",
        f"{weather['temperature']} °C"
    )


with c2:

    st.metric(
        "Humidity",
        f"{weather['humidity']} %"
    )


with c3:

    st.metric(
        "Rain",
        f"{weather['rain']} mm"
    )


with c4:

    st.metric(
        "Wind",
        f"{weather['wind']} km/h"
    )


with c5:

    if risk_level == "RED":

        st.metric(
            "Risk",
            f"{risk}% 🔴"
        )

    elif risk_level == "YELLOW":

        st.metric(
            "Risk",
            f"{risk}% 🟡"
        )

    else:

        st.metric(
            "Risk",
            f"{risk}% 🟢"
        )


st.caption(
    f"Updated: {weather['time']} | "
    f"Location: {selected_location} | "
    f"Coordinates: {LAT}, {LON} | "
    f"Condition: {weather_description(weather['weather_code'])}"
)


# =========================================================
# NEW: REAL-TIME HAZARD FEEDS ROW
# =========================================================

st.markdown("## 📡 Real-Time Hazard Feeds")

h1, h2, h3 = st.columns(3)

with h1:
    st.metric("Live Slope (Elevation API)", f"{live_slope}°")
    st.caption("Derived from Open-Meteo elevation samples around this point.")

with h2:
    if flood_data["available"]:
        st.metric("River Discharge", f"{flood_data['discharge']} m³/s")
    else:
        st.metric("River Discharge", "No nearby reach modeled")
    st.caption("Source: Open-Meteo Flood API (daily forecast).")

with h3:
    st.metric("Nearby Earthquakes (7d, M3.0+)", len(earthquakes))
    st.caption("Source: USGS, within 300km, last 7 days.")

if earthquakes:
    with st.expander(f"🌍 {len(earthquakes)} recent earthquake(s) nearby"):
        for q in earthquakes:
            st.write(
                f"**M{q['magnitude']}** — {q['place']} — {q['time']}"
            )


# =========================================================
# RISK STATUS
# =========================================================

if risk_level == "RED":

    st.markdown(
        f"""
        <div class="red-card">
        🔴 RED RISK — Current risk indicator is {risk}%.
        Immediate monitoring and evacuation planning should be considered.
        </div>
        """,
        unsafe_allow_html=True
    )

elif risk_level == "YELLOW":

    st.markdown(
        f"""
        <div class="yellow-card">
        🟡 YELLOW RISK — Current risk indicator is {risk}%.
        Continue monitoring weather and preparedness conditions.
        </div>
        """,
        unsafe_allow_html=True
    )

else:

    st.markdown(
        f"""
        <div class="green-card">
        🟢 GREEN RISK — Current risk indicator is {risk}%.
        Current environmental conditions are within the prototype's lower-risk range.
        </div>
        """,
        unsafe_allow_html=True
    )


# =========================================================
# MAIN LAYOUT
# =========================================================

left, right = st.columns(
    [2.1, 1]
)


# =========================================================
# MAP
# =========================================================

with left:

    st.markdown(
        '<div class="section-title">'
        '📍 Interactive Geo-Spatial Web Map'
        '</div>',
        unsafe_allow_html=True
    )

    # -----------------------------------------------------
    # PROTOTYPE ZONES
    # -----------------------------------------------------

    zones = [

        {
            "name": "High Risk Zone",
            "lat": LAT + 0.04,
            "lon": LON + 0.04,
            "population": 4200,
            "risk": 82
        },

        {
            "name": "Moderate Risk Zone",
            "lat": LAT - 0.05,
            "lon": LON + 0.06,
            "population": 1800,
            "risk": 58
        },

        {
            "name": "Low Risk Zone",
            "lat": LAT + 0.06,
            "lon": LON - 0.06,
            "population": 2700,
            "risk": 25
        }
    ]


    # -----------------------------------------------------
    # SAFE HUBS
    # -----------------------------------------------------

    hubs = [

        {
            "name": "Regional Relief Centre",
            "lat": LAT + 0.08,
            "lon": LON + 0.08,
            "capacity": 7000
        },

        {
            "name": "Community Safe Hub",
            "lat": LAT - 0.08,
            "lon": LON - 0.05,
            "capacity": 5000
        },

        {
            "name": "Emergency Shelter",
            "lat": LAT + 0.02,
            "lon": LON - 0.09,
            "capacity": 3500
        }
    ]


    # -----------------------------------------------------
    # CREATE MAP
    # -----------------------------------------------------

    m = folium.Map(
        location=[LAT, LON],
        zoom_start=9,
        tiles="OpenStreetMap"
    )


    # -----------------------------------------------------
    # CURRENT LOCATION
    # -----------------------------------------------------

    folium.Marker(
        [LAT, LON],
        tooltip=f"📍 {selected_location}",
        popup=(
            f"<b>{selected_location}</b><br>"
            f"Risk: {risk}%<br>"
            f"Level: {risk_level}<br>"
            f"Slope: {live_slope}°<br>"
            f"Weather: {weather_description(weather['weather_code'])}"
        ),
        icon=folium.Icon(
            color=risk_color(risk_level),
            icon="warning-sign"
        )
    ).add_to(m)


    # -----------------------------------------------------
    # CURRENT RISK CIRCLE
    # -----------------------------------------------------

    folium.Circle(
        location=[LAT, LON],
        radius=8000,
        color=risk_color(risk_level),
        fill=True,
        fill_opacity=0.20,
        popup=f"Current Risk: {risk}%"
    ).add_to(m)


    # -----------------------------------------------------
    # RISK ZONES
    # -----------------------------------------------------

    for zone in zones:

        zone_color = "red"

        if zone["risk"] < 40:
            zone_color = "green"

        elif zone["risk"] < 70:
            zone_color = "orange"

        folium.Circle(
            location=[
                zone["lat"],
                zone["lon"]
            ],
            radius=5000,
            color=zone_color,
            fill=True,
            fill_opacity=0.30,
            popup=(
                f"<b>{zone['name']}</b><br>"
                f"Risk: {zone['risk']}%<br>"
                f"Population: {zone['population']}"
            )
        ).add_to(m)

        folium.Marker(
            [
                zone["lat"],
                zone["lon"]
            ],
            tooltip=zone["name"],
            popup=(
                f"<b>{zone['name']}</b><br>"
                f"Risk: {zone['risk']}%<br>"
                f"Population: {zone['population']}"
            ),
            icon=folium.Icon(
                color=zone_color,
                icon="info-sign"
            )
        ).add_to(m)


    # -----------------------------------------------------
    # SAFE HUBS
    # -----------------------------------------------------

    for hub in hubs:

        folium.Marker(
            [
                hub["lat"],
                hub["lon"]
            ],
            tooltip=f"🏠 {hub['name']}",
            popup=(
                f"<b>{hub['name']}</b><br>"
                f"Capacity: {hub['capacity']} people"
            ),
            icon=folium.Icon(
                color="blue",
                icon="home"
            )
        ).add_to(m)


    # -----------------------------------------------------
    # NEW: LIVE EARTHQUAKE MARKERS
    # -----------------------------------------------------

    for q in earthquakes:

        folium.CircleMarker(
            location=[q["lat"], q["lon"]],
            radius=4 + q["magnitude"],
            color="purple",
            fill=True,
            fill_opacity=0.6,
            popup=(
                f"<b>Earthquake M{q['magnitude']}</b><br>"
                f"{q['place']}<br>{q['time']}"
            ),
            tooltip=f"M{q['magnitude']} earthquake"
        ).add_to(m)


    # -----------------------------------------------------
    # MAP LEGEND
    # -----------------------------------------------------

    legend_html = """
    <div style="
        position: fixed;
        bottom: 25px;
        left: 25px;
        width: 200px;
        background-color: white;
        border: 2px solid grey;
        z-index: 9999;
        padding: 10px;
        border-radius: 8px;
        font-size: 14px;
    ">

    <b>Risk Legend</b><br><br>

    <span style="color:red;">●</span>
    Red - High Risk<br>

    <span style="color:orange;">●</span>
    Yellow - Moderate Risk<br>

    <span style="color:green;">●</span>
    Green - Low Risk<br>

    <span style="color:blue;">●</span>
    Blue - Safe Hub<br>

    <span style="color:purple;">●</span>
    Purple - Recent Earthquake

    </div>
    """

    m.get_root().html.add_child(
        folium.Element(legend_html)
    )


    # -----------------------------------------------------
    # DISPLAY MAP
    # -----------------------------------------------------

    st_folium(
        m,
        width=None,
        height=600,
        returned_objects=[]
    )


# =========================================================
# RIGHT PANEL
# =========================================================

with right:

    st.markdown(
        "## 🚨 Risk & Relocation"
    )

    st.metric(
        "Current Risk",
        f"{risk}%"
    )

    st.metric(
        "Risk Level",
        risk_level
    )

    st.metric(
        "Live Slope",
        f"{live_slope}°"
    )

    st.markdown("---")

    st.markdown("### 🏠 Relocation Queue")

    evacuation_zones = [
        zone for zone in zones
        if zone["risk"] >= threshold
    ]

    if evacuation_zones:

        for zone in evacuation_zones:

            st.warning(
                f"🚨 {zone['name']} | "
                f"Risk {zone['risk']}% | "
                f"Population {zone['population']}"
            )

    else:

        st.success(
            "No prototype zone currently exceeds the selected threshold."
        )


# =========================================================
# ALERTS
# =========================================================

st.markdown("---")

st.markdown(
    '<div class="section-title">🚨 Disaster Alerts</div>',
    unsafe_allow_html=True
)


if earthquakes and max(q["magnitude"] for q in earthquakes) >= 5.0:

    st.error(
        "🌍 A significant earthquake (M5.0+) has been detected nearby in the last 7 days."
    )

elif weather["weather_code"] in [95, 96, 99]:

    st.error(
        "⛈️ Thunderstorm-related weather condition detected."
    )

elif flood_data["available"] and flood_data["discharge"] and flood_data["discharge"] > 400:

    st.warning(
        "🌊 Elevated river discharge detected — flood risk should be monitored."
    )

elif weather["rain"] > 10:

    st.warning(
        "🌧️ Significant rain condition detected. Continue monitoring."
    )

elif risk >= threshold:

    st.warning(
        "⚠️ Current live risk indicator has crossed the configured threshold."
    )

else:

    st.success(
        "✅ No immediate alert condition detected from live feeds."
    )


# =========================================================
# RELOCATION CENTERS
# =========================================================

st.markdown("---")

st.markdown(
    '<div class="section-title">🏠 Relocation & Safe Centres</div>',
    unsafe_allow_html=True
)


hub_rows = []

for hub in hubs:

    hub_rows.append(
        {
            "Safe Centre": hub["name"],
            "Capacity": hub["capacity"],
            "Water Need / Day": hub["capacity"] * water_norm,
            "Land Requirement": hub["capacity"] * land_norm
        }
    )

st.dataframe(
    hub_rows,
    use_container_width=True,
    hide_index=True
)


# =========================================================
# CARRYING CAPACITY
# =========================================================

st.markdown("---")

st.markdown(
    '<div class="section-title">📊 Carrying Capacity Analysis</div>',
    unsafe_allow_html=True
)


total_capacity = sum(
    hub["capacity"] for hub in hubs
)

daily_water = total_capacity * water_norm

land_requirement = total_capacity * land_norm


cc1, cc2, cc3 = st.columns(3)


with cc1:

    st.metric(
        "Total Shelter Capacity",
        f"{total_capacity:,}"
    )


with cc2:

    st.metric(
        "Daily Water Requirement",
        f"{daily_water:,} L"
    )


with cc3:

    st.metric(
        "Land Requirement",
        f"{land_requirement:,} sq.m"
    )


# =========================================================
# RELIEF FUND
# =========================================================
# (rest of original app continues below unchanged, if present)
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.enums import TA_CENTER
from io import BytesIO
from datetime import datetime
def generate_pdf(state, temperature, humidity, rainfall, wind_speed,
                 condition, risk_score):

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()

    title = styles["Title"]
    title.alignment = TA_CENTER

    story = []

    story.append(Paragraph("WEATHER & DISASTER RISK REPORT", title))
    story.append(Spacer(1, 20))

    story.append(
        Paragraph(
            f"<b>Generated:</b> {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}",
            styles["Normal"]
        )
    )

    story.append(Spacer(1, 15))

    data = [
        ["Parameter", "Value"],
        ["Location / State", state],
        ["Temperature", f"{temperature} °C"],
        ["Humidity", f"{humidity} %"],
        ["Rainfall", f"{rainfall} mm"],
        ["Wind Speed", f"{wind_speed} km/h"],
        ["Predicted Condition", condition],
        ["Risk Score", f"{risk_score}%"]
    ]

    table = Table(data, colWidths=[220, 220])

    table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
            ("PADDING", (0, 0), (-1, -1), 8),
        ])
    )

    story.append(table)
    story.append(Spacer(1, 20))

    if condition == "Safe":
        recommendation = "Current weather conditions are relatively safe. Continue monitoring weather updates."
    else:
        recommendation = "Risk conditions detected. Monitor official weather alerts and follow local disaster-management instructions."

    story.append(
        Paragraph(
            f"<b>Recommendation:</b> {recommendation}",
            styles["Normal"]
        )
    )

    doc.build(story)

    buffer.seek(0)
    return buffer
"""
report_generator.py
--------------------
Builds a PDF snapshot of the current risk dashboard: live weather,
slope, flood/earthquake feeds, the risk classification, the
relocation queue, and carrying-capacity numbers.

Usage (from app.py):

    from report_generator import generate_risk_report_pdf

    pdf_bytes = generate_risk_report_pdf(
        location_name=selected_location,
        lat=LAT, lon=LON,
        weather=weather, weather_condition=weather_description(weather['weather_code']),
        live_slope=live_slope,
        flood_data=flood_data,
        earthquakes=earthquakes,
        risk=risk, risk_level=risk_level,
        evacuation_zones=evacuation_zones,
        hubs=hubs,
        total_capacity=total_capacity, daily_water=daily_water,
        land_requirement=land_requirement,
    )

    st.download_button(
        "📄 Download Risk Report (PDF)",
        data=pdf_bytes,
        file_name="pranaraksha_risk_report.pdf",
        mime="application/pdf",
    )

This returns raw PDF bytes in memory -- nothing is written to disk,
so it works the same locally and when deployed.
"""

import io
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)


RISK_COLORS = {
    "RED": colors.HexColor("#9b1c1c"),
    "YELLOW": colors.HexColor("#795900"),
    "GREEN": colors.HexColor("#176b3a"),
}


def _build_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="ReportTitle",
        parent=styles["Title"],
        fontSize=22,
        textColor=colors.HexColor("#202735"),
    ))

    styles.add(ParagraphStyle(
        name="ReportSubtitle",
        parent=styles["Normal"],
        fontSize=11,
        textColor=colors.HexColor("#707070"),
        spaceAfter=14,
    ))

    styles.add(ParagraphStyle(
        name="SectionHeading",
        parent=styles["Heading2"],
        fontSize=14,
        textColor=colors.HexColor("#202735"),
        spaceBefore=16,
        spaceAfter=8,
    ))

    styles.add(ParagraphStyle(
        name="RiskBanner",
        parent=styles["Normal"],
        fontSize=13,
        leading=17,
    ))

    return styles


def generate_risk_report_pdf(
    location_name,
    lat,
    lon,
    weather,
    weather_condition,
    live_slope,
    flood_data,
    earthquakes,
    risk,
    risk_level,
    evacuation_zones,
    hubs,
    total_capacity,
    daily_water,
    land_requirement,
):
    """Builds the PDF in memory and returns it as bytes."""

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        title="PRANARAKSHA AI Risk Report",
    )

    styles = _build_styles()
    story = []

    # ---------------------------------------------------
    # Header
    # ---------------------------------------------------

    story.append(Paragraph("PRANARAKSHA AI", styles["ReportTitle"]))
    story.append(Paragraph(
        "Carrying Capacity &amp; Hazard Relocation Engine — Risk Report",
        styles["ReportSubtitle"]
    ))

    generated_at = datetime.now().strftime("%d %b %Y, %H:%M")

    story.append(Paragraph(
        f"<b>Location:</b> {location_name} &nbsp;&nbsp; "
        f"<b>Coordinates:</b> {lat}, {lon} &nbsp;&nbsp; "
        f"<b>Generated:</b> {generated_at}",
        styles["Normal"]
    ))

    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", color=colors.HexColor("#dddddd")))
    story.append(Spacer(1, 10))

    # ---------------------------------------------------
    # Risk banner
    # ---------------------------------------------------

    risk_color = RISK_COLORS.get(risk_level, colors.black)

    story.append(Paragraph(
        f'<font color="{risk_color.hexval()}"><b>{risk_level} RISK — {risk}%</b></font>',
        styles["RiskBanner"]
    ))
    story.append(Spacer(1, 6))

    # ---------------------------------------------------
    # Live environmental conditions
    # ---------------------------------------------------

    story.append(Paragraph("Live Environmental Conditions", styles["SectionHeading"]))

    env_rows = [
        ["Temperature", f"{weather['temperature']} °C"],
        ["Humidity", f"{weather['humidity']} %"],
        ["Rain", f"{weather['rain']} mm"],
        ["Wind", f"{weather['wind']} km/h"],
        ["Condition", weather_condition],
    ]

    story.append(_make_table(["Metric", "Value"], env_rows))

    # ---------------------------------------------------
    # Real-time hazard feeds
    # ---------------------------------------------------

    story.append(Paragraph("Real-Time Hazard Feeds", styles["SectionHeading"]))

    flood_text = (
        f"{flood_data['discharge']} m3/s"
        if flood_data.get("available") else "No nearby reach modeled"
    )

    hazard_rows = [
        ["Live Slope (Elevation API)", f"{live_slope}°"],
        ["River Discharge (Flood API)", flood_text],
        ["Nearby Earthquakes (7d, M3.0+)", str(len(earthquakes))],
    ]

    story.append(_make_table(["Feed", "Value"], hazard_rows))

    if earthquakes:
        story.append(Spacer(1, 8))
        story.append(Paragraph("Recent earthquakes:", styles["Normal"]))
        quake_rows = [
            [f"M{q['magnitude']}", q["place"], q["time"]]
            for q in earthquakes
        ]
        story.append(_make_table(["Magnitude", "Location", "Time (UTC)"], quake_rows))

    # ---------------------------------------------------
    # Relocation queue
    # ---------------------------------------------------

    story.append(Paragraph("Relocation Queue", styles["SectionHeading"]))

    if evacuation_zones:
        zone_rows = [
            [z["name"], f"{z['risk']}%", f"{z['population']:,}"]
            for z in evacuation_zones
        ]
        story.append(_make_table(["Zone", "Risk", "Population"], zone_rows))
    else:
        story.append(Paragraph(
            "No zone currently exceeds the configured risk threshold.",
            styles["Normal"]
        ))

    # ---------------------------------------------------
    # Relocation & safe centres
    # ---------------------------------------------------

    story.append(Paragraph("Relocation &amp; Safe Centres", styles["SectionHeading"]))

    hub_rows = [
        [h["name"], f"{h['capacity']:,}"]
        for h in hubs
    ]
    story.append(_make_table(["Safe Centre", "Capacity"], hub_rows))

    # ---------------------------------------------------
    # Carrying capacity
    # ---------------------------------------------------

    story.append(Paragraph("Carrying Capacity Analysis", styles["SectionHeading"]))

    capacity_rows = [
        ["Total Shelter Capacity", f"{total_capacity:,}"],
        ["Daily Water Requirement", f"{daily_water:,} L"],
        ["Land Requirement", f"{land_requirement:,} sq.m"],
    ]
    story.append(_make_table(["Metric", "Value"], capacity_rows))

    # ---------------------------------------------------
    # Footer note
    # ---------------------------------------------------

    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", color=colors.HexColor("#dddddd")))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "This report reflects a prototype risk indicator based on live weather, "
        "elevation, river discharge, and seismic feeds combined with placeholder "
        "GIS zones. It is a decision-support aid, not an official hazard warning.",
        styles["ReportSubtitle"]
    ))

    doc.build(story)

    buffer.seek(0)
    return buffer.getvalue()


def _make_table(header, rows):
    data = [header] + rows

    table = Table(data, hAlign="LEFT", colWidths=None)

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#202735")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f7f7")]),
        ("TOPPADDING", (0, 1), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))

    return table



pdf_bytes = generate_risk_report_pdf(
    location_name=selected_location,
    lat=LAT, lon=LON,
    weather=weather, weather_condition=weather_description(weather['weather_code']),
    live_slope=live_slope,
    flood_data=flood_data,
    earthquakes=earthquakes,
    risk=risk, risk_level=risk_level,
    evacuation_zones=evacuation_zones,
    hubs=hubs,
    total_capacity=total_capacity, daily_water=daily_water,
    land_requirement=land_requirement,
)

st.download_button(
    "📄 Download Risk Report (PDF)",
    data=pdf_bytes,
    file_name="pranaraksha_risk_report.pdf",
    mime="application/pdf",
)