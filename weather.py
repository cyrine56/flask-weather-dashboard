from flask import Flask, render_template, request
import requests
from datetime import datetime, timedelta

app = Flask(__name__)

API_KEY = "11a11126c52412d424dcb79a284bf934"  # remplace par ta clé si besoin
BASE_URL_CURRENT = "https://api.openweathermap.org/data/2.5/weather"
BASE_URL_FORECAST = "https://api.openweathermap.org/data/2.5/forecast"

DEFAULT_CITIES = ["Tunis", "Paris", "New York", "London"]


def to_local_time(utc_ts, tz_offset):
    """utc_ts (seconds) + tz_offset (seconds) -> 'HH:MM' """
    return (datetime.utcfromtimestamp(utc_ts) + timedelta(seconds=tz_offset)).strftime("%H:%M")

def get_weather(city):
    params = {
        "q": city,
        "appid": API_KEY,
        "units": "metric",
        "lang": "fr",
    }
    try:
        r = requests.get(BASE_URL_CURRENT, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data.get("cod") != 200:
            return None
    except requests.exceptions.RequestException:
        return None

    tz = data.get("timezone", 0)
    now_local = to_local_time(data.get("dt", int(datetime.utcnow().timestamp())), tz)

    city_name = data["name"]
    if city_name.lower() == "tunisia":  # parfois OpenWeather met le nom du pays
        city_name = "Tunis"

    return {
        "city": city_name,
        "country": data["sys"].get("country"),
        "description": data["weather"][0]["description"].capitalize(),
        "temp": round(data["main"]["temp"]),
        "feels_like": round(data["main"]["feels_like"]),
        "humidity": data["main"]["humidity"],
        "wind": round(data["wind"]["speed"]),
        "icon": data["weather"][0]["icon"],
        "time_local": now_local,
        "timezone": tz,
        "lat": data["coord"]["lat"],
        "lon": data["coord"]["lon"],
    }


def get_forecast(city):
    """
    Renvoie:
      - hourly (3 créneaux à venir)
      - daily (3 jours, une valeur par jour vers midi si possible)
    """
    params = {
        "q": city,
        "appid": API_KEY,
        "units": "metric",
        "lang": "fr",
    }
    try:
        r = requests.get(BASE_URL_FORECAST, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data.get("cod") != "200":
            return {"hourly": [], "daily": []}
    except requests.exceptions.RequestException:
        return {"hourly": [], "daily": []}

    tz = data["city"].get("timezone", 0)

    # --- Prochains créneaux horaires (OpenWeather = pas de 3h)
    hourly = []
    for entry in data["list"][:3]:
        # entry["dt"] est en UTC (seconds)
        time_local = (datetime.utcfromtimestamp(entry["dt"]) + timedelta(seconds=tz)).strftime("%H:%M")
        hourly.append({
            "time": time_local,
            "temp": round(entry["main"]["temp"]),
            "icon": entry["weather"][0]["icon"],
            "desc": entry["weather"][0]["description"].capitalize()
        })

    # --- Daily sur 3 jours: on regroupe par date locale et on choisit le créneau ~12:00 si dispo
    days = {}
    for entry in data["list"]:
        local_dt = datetime.utcfromtimestamp(entry["dt"]) + timedelta(seconds=tz)
        key = local_dt.strftime("%Y-%m-%d")
        days.setdefault(key, []).append(entry)

    daily = []
    for day, entries in list(days.items())[:3]:
        # pick item closest to 12:00
        target = datetime.strptime(day + " 12:00", "%Y-%m-%d %H:%M")
        chosen = min(entries, key=lambda e: abs((datetime.utcfromtimestamp(e["dt"]) + timedelta(seconds=tz)) - target))
        local_dt = datetime.utcfromtimestamp(chosen["dt"]) + timedelta(seconds=tz)
        daily.append({
            "weekday": local_dt.strftime("%a"),  # Lun, Mar, ...
            "desc": chosen["weather"][0]["description"].capitalize(),
            "icon": chosen["weather"][0]["icon"],
            "tmax": round(chosen["main"]["temp_max"]),
            "tmin": round(chosen["main"]["temp_min"]),
        })

    return {"hourly": hourly, "daily": daily}

@app.route("/", methods=["GET", "POST"])
def index():
    search_city = None
    if request.method == "POST":
        search_city = request.form.get("city", "").strip()

    # météo des villes par défaut (pour la liste "Latest searches")
    default_weather = []
    for c in DEFAULT_CITIES:
        w = get_weather(c)
        if w: default_weather.append(w)

    # bloc de droite (ville sélectionnée ou 1ère par défaut)
    if search_city:
        selected = get_weather(search_city)
    else:
        selected = default_weather[0] if default_weather else None

    hourly = []
    daily = []
    if selected:
        fc = get_forecast(selected["city"])
        hourly = fc["hourly"]
        daily = fc["daily"]

    return render_template(
        "index.html",
        default_weather=default_weather,
        selected=selected,
        hourly=hourly,
        daily=daily
    )

if __name__ == "__main__":
    app.run(debug=True)
