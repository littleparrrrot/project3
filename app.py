from flask import Flask, request, render_template
import requests


app = Flask(__name__)

API_KEY = "4zPGFpnLptk5jkr9Gf7cZc0noNwcOtg2"
BASE_URL = "http://dataservice.accuweather.com/forecasts/v1/daily/1day/"

def get_weather(location_key):
    try:
        url = f"{BASE_URL}{location_key}?apikey={API_KEY}&metric=true"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Ошибка при запросе данных: {e}")
        return None

def get_current_conditions(location_key):
    try:
        url = f"http://dataservice.accuweather.com/currentconditions/v1/{location_key}?apikey={API_KEY}&details=true"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if data:
            return data[0]
        return None
    except Exception as e:
        print(f"Ошибка при запросе текущих условий: {e}")
        return None


def check_bad_weather(temperature, wind_speed, precipitation_probability):
    if temperature < -30 or temperature > 35:
        return "Плохая погода: экстремальная температура."
    if wind_speed > 50:
        return "Плохая погода: сильный ветер."
    if precipitation_probability > 70:
        return "Плохая погода: высокая вероятность осадков."
    return "Погода хорошая."

def get_location_key(city):
    try:
        url = f"http://dataservice.accuweather.com/locations/v1/cities/search?apikey={API_KEY}&q={city}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if data:
            return data[0]["Key"]
        else:
            return None
    except Exception as e:
        print(f"Ошибка при поиске города: {e}")
        return None


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        start_city = request.form.get("start_city")
        end_city = request.form.get("end_city")

        if not start_city or not end_city:
            return "<p>Ошибка: Пожалуйста, введите оба города.</p><a href='/'>Вернуться назад</a>"

        results = []
        for city in [start_city, end_city]:
            try:
                location_key = get_location_key(city)
                if location_key:
                    current_data = get_current_conditions(location_key)
                    weather_data = get_weather(location_key)
                    if current_data and weather_data:
                        forecast = weather_data["DailyForecasts"][0]
                        temperature = forecast.get("Temperature", {}).get("Maximum", {}).get("Value", "N/A")
                        wind_speed = current_data.get("Wind", {}).get("Speed", {}).get("Metric", {}).get("Value", 0)
                        humidity = current_data.get("RelativeHumidity", "N/A")

                        has_precipitation = current_data.get("HasPrecipitation", False)
                        precipitation_type = current_data.get("PrecipitationType", "")

                        if has_precipitation and precipitation_type == "Rain":
                            rain_probability = 100
                        else:
                            rain_probability = forecast.get("Day", {}).get("RainProbability", 0)

                        weather_result = check_bad_weather(temperature, wind_speed, rain_probability)
                        results.append({
                            "city": city,
                            "temperature": temperature,
                            "wind_speed": wind_speed,
                            "rain_probability": rain_probability,
                            "humidity": humidity,
                            "weather_result": weather_result
                        })
                    else:
                        results.append({"city": city, "error": "Ошибка при получении данных о погоде"})
                else:
                    results.append({"city": city, "error": "Город не найден"})
            except Exception as e:
                results.append({"city": city, "error": f"Ошибка: {str(e)}"})

        response = "<h1>Прогноз погоды для маршрута</h1>"
        for result in results:
            if "error" in result:
                response += f"<p><strong>{result['city']}</strong>: {result['error']}</p>"
            else:
                response += f"""
                <h2>{result['city']}</h2>
                <p>Температура: {result['temperature']}°C</p>
                <p>Скорость ветра: {result['wind_speed']} км/ч</p>
                <p>Вероятность дождя: {result['rain_probability']}%</p>
                <p>Влажность: {result['humidity']}%</p>
                <p>Результат: {result['weather_result']}</p>
                """
        response += '<a href="/">Вернуться назад</a>'
        return response

    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)