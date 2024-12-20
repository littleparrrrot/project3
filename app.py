from flask import Flask, request, render_template
from dash import Dash, dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objs as go
import requests


app = Flask(__name__)
app_dash = Dash(__name__, server=app, url_base_pathname='/dash/')

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

def get_city_weather(city_name):
    url = f"http://dataservice.accuweather.com/locations/v1/cities/search?apikey={API_KEY}&q={city_name}"
    response = requests.get(url)
    if response.status_code != 200 or not response.json():
        print(f"Ошибка: Город '{city_name}' не найден.")
        return None

    city_data = response.json()[0]
    location_key = city_data["Key"]
    latitude = city_data["GeoPosition"]["Latitude"]
    longitude = city_data["GeoPosition"]["Longitude"]

    weather_data = get_weather(location_key)
    if not weather_data:
        print(f"Ошибка: Не удалось получить данные о погоде для города '{city_name}'.")
        return None

    forecast = weather_data["DailyForecasts"][0]
    return {
        "city": city_name,
        "latitude": latitude,
        "longitude": longitude,
        "temperature": forecast["Temperature"]["Maximum"]["Value"],
        "rain_probability": forecast["Day"].get("RainProbability", 0)
    }

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


app_dash.layout = html.Div([
    html.H1("Прогноз погоды для маршрута"),
    dcc.Graph(id='route-weather-graph'),
    html.Div([
        dcc.Textarea(
            id='cities-input',
            placeholder='Введите города через запятую (например, Москва, Санкт-Петербург)',
            style={'width': '100%', 'height': 100},
        ),
        html.Button('Обновить маршрут', id='update-route-button', n_clicks=0)
    ])
])


app_dash_routes = Dash(__name__, server=app, url_base_pathname='/dash/route/')
app_dash_routes.layout = html.Div([
    html.H1("Маршрут с прогнозом погоды"),
    dcc.Textarea(
        id='cities-input-route',
        placeholder='Введите города через запятую (например, Москва, Санкт-Петербург)',
        style={'width': '100%', 'height': 100},
    ),
    html.Button('Обновить маршрут', id='update-route-button-route', n_clicks=0),
    dcc.Graph(id='route-map')
])

@app_dash_routes.callback(
    Output('route-map', 'figure'),
    [Input('cities-input-route', 'value')]
)

def update_route_map(cities_input):
    if not cities_input:
        return go.Figure()

    cities = [city.strip() for city in cities_input.split(',')]
    return create_route_map(cities)

def update_route_weather_graph_route(cities_input, parameter):
    if not cities_input or not parameter:
        return go.Figure()

    cities = [city.strip() for city in cities_input.split(',')]
    data = []
    dates = []

    for city in cities:
        location_key = get_location_key(city)
        if not location_key:
            continue

        weather_data = get_weather(location_key)
        if not weather_data:
            continue

        forecast = weather_data["DailyForecasts"]

        city_dates = [day["Date"] for day in forecast]
        if parameter == 'Temperature':
            values = [day["Temperature"]["Maximum"]["Value"] for day in forecast]
        elif parameter == 'RainProbability':
            values = [day["Day"].get("RainProbability", 0) for day in forecast]
        elif parameter == 'WindSpeed':
            values = [day["Day"].get("Wind", {}).get("Speed", {}).get("Value", 0) for day in forecast]
        else:
            continue

        if not dates:
            dates = city_dates
        data.append(go.Scatter(
            x=city_dates, y=values, mode='lines+markers', name=f"{city} ({parameter})"
        ))

    figure = go.Figure(
        data=data,
        layout=go.Layout(
            title=f'Прогноз {parameter} для маршрута',
            xaxis=dict(title='Дата'),
            yaxis=dict(title=parameter)
        )
    )
    return figure

def create_route_map(cities):
    lats, lons, locations, temperatures, rain_probabilities = [], [], [], [], []

    for city in cities:
        city_data = get_city_weather(city)
        if not city_data:
            continue

        lats.append(city_data["latitude"])
        lons.append(city_data["longitude"])
        locations.append(city_data["city"])
        temperatures.append(city_data["temperature"])
        rain_probabilities.append(city_data["rain_probability"])

    fig = go.Figure()

    fig.add_trace(go.Scattergeo(
        locationmode='ISO-3',
        lon=lons,
        lat=lats,
        text=[
            f"{loc}<br>Температура: {temp}°C<br>Вероятность дождя: {rain}%"
            for loc, temp, rain in zip(locations, temperatures, rain_probabilities)
        ],
        mode='markers+lines',
        marker=dict(size=10, color='blue'),
        name="Маршрут"
    ))

    fig.update_layout(
        title="Маршрут с прогнозом погоды",
        geo=dict(
            scope='world',
            projection_type='natural earth',
            showland=True,
            landcolor="rgb(217, 217, 217)",
            showcountries=True,
            countrycolor="rgb(255, 255, 255)"
        )
    )

    return fig

@app.route("/")
def home():
    return '''
    <h1>Прогноз погоды</h1>
    <p><a href="/dash/">Графики для одного города</a></p>
    <p><a href="/dash/route">Графики для маршрута</a></p>
    '''

if __name__ == "__main__":
    app.run(debug=True)