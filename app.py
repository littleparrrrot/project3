from flask import Flask, request, render_template
from dash import Dash, dcc, html
from dash.dependencies import Input, Output, State
import plotly.graph_objs as go
import requests


app = Flask(__name__)
app_dash = Dash(__name__, server=app, url_base_pathname='/dash/')

API_KEY = "QJ82ByarvAoGA37HJ4rpCYvlIDnYrAED"
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

    current_data = get_current_conditions(location_key)
    weather_data = get_weather(location_key)
    if not weather_data:
        print(f"Ошибка: Не удалось получить данные о погоде для города '{city_name}'.")
        return None

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

    return {
        "city": city_name,
        "latitude": latitude,
        "longitude": longitude,
        "temperature": f"{temperature} °C",
        "rain_probability": f"{rain_probability} %",
        "wind_speed": f"{wind_speed} м/с",
        "humidity": f"{humidity} %",
        "result": f"{weather_result}"
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
        start_point = request.form.get("start_point")
        end_point = request.form.get("end_point")
        extra_points = request.form.get("extra_points", "")
        parameter = request.form.get("parameter", "Temperature")

        cities = [start_point] + [city.strip() for city in extra_points.split(',') if city.strip()] + [end_point]

        weather_data = {}
        for city in cities:
            city_data = get_city_weather(city)
            if city_data:
                weather_data[city_data["city"]] = {
                    "Температура": city_data["temperature"],
                    "Скорость ветра": city_data["wind_speed"],
                    "Влажность": city_data["humidity"],
                    "Вероятность дождя": city_data["rain_probability"]
                }

        print("Собранные данные о погоде:", weather_data)

        map_html = create_route_map(cities, parameter)._repr_html_()

        graph_content = create_weather_graph(cities, parameter)

        return render_template(
            "index.html",
            weather_data=weather_data,
            map_html=map_html,
            graph_html=graph_content,
            parameter=parameter
        )

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
    html.H1("Маршрут и данные о погоде"),
    dcc.Textarea(
        id='cities-input-route',
        placeholder='Введите города через запятую (например, Москва, Санкт-Петербург)',
        style={'width': '100%', 'height': 100},
    ),
    html.Button('Обновить маршрут', id='update-route-button-route', n_clicks=0),
    html.Div([
        dcc.Input(
            id='min-temperature-input',
            type='number',
            placeholder='Минимальная температура',
            style={'width': '50%'}
        ),
        dcc.Dropdown(
            id='parameter-dropdown',
            options=[
                {'label': 'Температура', 'value': 'Temperature'},
                {'label': 'Вероятность дождя', 'value': 'RainProbability'},
                {'label': 'Скорость ветра', 'value': 'WindSpeed'},
                {'label': 'Влажность', 'value': 'Humidity'}
            ],
            value='Temperature',
            placeholder='Выберите параметр',
        )
    ]),
    html.Div([
        dcc.Graph(id='route-map', style={'display': 'inline-block', 'width': '48%'}),
        dcc.Graph(id='weather-graph', style={'display': 'inline-block', 'width': '48%'})
    ])
])


def create_weather_graph(cities, parameter):
    values = []
    labels = []
    rain_probabilities = {}

    for city in cities:
        city_data = get_city_weather(city)
        if not city_data:
            continue
        labels.append(city)

        if parameter == "Temperature":
            values.append(float(city_data["temperature"].split()[0]))  # Убираем °C
        elif parameter == "WindSpeed":
            values.append(float(city_data["wind_speed"].split()[0]))  # Убираем м/с
        elif parameter == "Humidity":
            values.append(float(city_data["humidity"].split()[0]))  # Убираем %
        elif parameter == "RainProbability":
            rain_probability = city_data["rain_probability"]
            rain_probabilities[city] = rain_probability

    if parameter == "RainProbability":
        return f"<ul>" + "".join(
            [f"<li>{city}: {rain_probability}</li>" for city, rain_probability in rain_probabilities.items()]
        ) + "</ul>"

    fig = go.Figure(
        data=[go.Bar(
            x=labels,
            y=values,
            text=values,
            textposition='auto',
            marker=dict(color='blue')
        )],
        layout=go.Layout(
            title=f"График {parameter} по городам маршрута",
            xaxis=dict(title="Города"),
            yaxis=dict(title=parameter),  # Убираем фиксированный диапазон для оси OY
        )
    )
    return fig.to_html(full_html=False)


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

def create_route_map(cities, parameter):
    lats, lons, locations, values = [], [], [], []

    for city in cities:
        city_data = get_city_weather(city)
        if not city_data:
            print(f"Ошибка: данные для города '{city}' отсутствуют.")
            continue

        lats.append(city_data["latitude"])
        lons.append(city_data["longitude"])
        locations.append(city_data["city"])

        if parameter == 'Temperature':
            values.append(city_data["temperature"])
        elif parameter == 'RainProbability':
            values.append(city_data["rain_probability"])
        elif parameter == 'WindSpeed':
            values.append(city_data["wind_speed"])
        elif parameter == 'Humidity':
            values.append(city_data["humidity"])
        else:
            values.append("Нет данных")

    fig = go.Figure()

    fig.add_trace(go.Scattergeo(
        locationmode='ISO-3',
        lon=lons,
        lat=lats,
        mode='lines',
        line=dict(width=2, color='blue'),
        name="Линия маршрута"
    ))

    fig.add_trace(go.Scattergeo(
        locationmode='ISO-3',
        lon=lons,
        lat=lats,
        text=[
            f"{loc}<br>Широта: {lat}<br>Долгота: {lon}<br>{parameter}: {value}"
            for loc, lat, lon, value in zip(locations, lats, lons, values)
        ],
        mode='markers',
        marker=dict(size=10, color='red', symbol='circle'),
        name="Города"
    ))

    fig.update_layout(
        title=f"Маршрут с прогнозом: {parameter}",
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

@app_dash_routes.callback(
    [Output('route-map', 'figure'),
     Output('weather-graph', 'figure')],
    [Input('update-route-button-route', 'n_clicks')],
    [State('cities-input-route', 'value'),
     State('parameter-dropdown', 'value'),
     State('min-temperature-input', 'value')]
)
def update_route_and_graph(n_clicks, cities_input, parameter, min_temp):
    if n_clicks is None or not cities_input or not parameter:
        return go.Figure(), go.Figure()

    cities = [city.strip() for city in cities_input.split(',')]
    filtered_cities = []
    weather_data = {"dates": [], "values": [], "labels": []}

    for city in cities:
        city_data = get_city_weather(city)
        if not city_data:
            continue

        if min_temp is not None and city_data["temperature"] < min_temp:
            continue

        filtered_cities.append(city)

        weather_data["dates"].append(city)
        if parameter == 'Temperature':
            weather_data["values"].append(city_data["temperature"])
        elif parameter == 'RainProbability':
            weather_data["values"].append(city_data["rain_probability"])
        elif parameter == 'WindSpeed':
            weather_data["values"].append(city_data["wind_speed"])
        elif parameter == 'Humidity':
            weather_data["values"].append(city_data["humidity"])
        weather_data["labels"].append(parameter)

    route_map = create_route_map(filtered_cities, parameter)

    weather_graph = go.Figure(
        data=[go.Bar(
            x=weather_data["dates"],
            y=weather_data["values"],
            text=weather_data["values"],
            textposition='auto',
            marker=dict(color='orange')
        )],
        layout=go.Layout(
            title=f"График {parameter} по городам маршрута",
            xaxis=dict(title="Города"),
            yaxis=dict(title=parameter)
        )
    )

    return route_map, weather_graph


if __name__ == "__main__":
    app.run(debug=True)