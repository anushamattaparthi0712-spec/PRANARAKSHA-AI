from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)


@app.route("/")
def home():
    return "PranaRaksha AI Backend is Running"


@app.route("/calculate-risk", methods=["POST"])
def calculate_risk():

    data = request.get_json()

    rainfall = float(data.get("rainfall", 150))
    slope = float(data.get("slope", 15))
    soil = float(data.get("soil", 40))
    population = float(data.get("population", 45))

    # Normalize rainfall
    rain_risk = min((rainfall / 350) * 100, 100)

    # Normalize slope
    slope_risk = min((slope / 45) * 100, 100)

    soil_risk = soil
    population_risk = population

    # Hazard calculation
    hazard = (
        rain_risk * 0.50
        + slope_risk * 0.30
        + soil_risk * 0.20
    )

    # Vulnerability
    vulnerability = (
        population_risk * 0.70
        + 30
    )

    # Exposure
    exposure = (
        population_risk * 0.70
        + 30
    )

    # Final risk
    risk = (
        hazard * 0.50
        + vulnerability * 0.30
        + exposure * 0.20
    )

    risk = round(min(risk, 100))

    # Risk classification
    if risk >= 70:
        status = "HIGH RISK"
        color = "red"

    elif risk >= 40:
        status = "MODERATE RISK"
        color = "yellow"

    else:
        status = "LOWER RISK"
        color = "green"

    return jsonify({
        "risk": risk,
        "status": status,
        "color": color,
        "rainfall": rainfall,
        "slope": slope,
        "soil": soil,
        "population": population
    })


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )