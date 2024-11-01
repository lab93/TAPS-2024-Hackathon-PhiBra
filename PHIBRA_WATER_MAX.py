# -*- coding: utf-8 -*-
"""
Integrated PHIBRA MAX WATER Dashboard with Agricultural Decision Support Dashboard
Created on Thu Oct 31 10:00:00 2024

Developed by Lucas Batista and Menard Soni.
"""

import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
import requests
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
import base64
import logging
import datetime
import webbrowser
import dash_daq as daq  # For additional UI components
import flask  # For server-side caching
import threading
from time import sleep
import os  # For handling file paths

# Initialize logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize the Dash app with Bootstrap theme
app = dash.Dash(
    __name__,
    suppress_callback_exceptions=True,
    external_stylesheets=[dbc.themes.BOOTSTRAP]
)
server = app.server

# Cache configuration (optional for performance optimization)
cache = flask.Flask(__name__)

# ----------------------------- IMAGE ENCODING ----------------------------- #

# Path to the image
IMAGE_PATH = r"C:\Users\lab93\Desktop\data\image8.JPG"

# Check if the image exists
if os.path.exists(IMAGE_PATH):
    with open(IMAGE_PATH, 'rb') as image_file:
        encoded_image = base64.b64encode(image_file.read()).decode('ascii')
    logger.debug("Image loaded and encoded successfully.")
else:
    encoded_image = None
    logger.error(f"Image not found at path: {IMAGE_PATH}")

# ----------------------------- PHIBRA MAX WATER DASHBOARD FUNCTIONS ----------------------------- #

# Function to get gridpoint information by latitude and longitude
def get_gridpoint_by_coords(lat, lon):
    url = f"https://api.weather.gov/points/{lat},{lon}"
    headers = {'User-Agent': 'YourAppName (youremail@example.com)'}  # Replace with your app name and email
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            gridX = data['properties']['gridX']
            gridY = data['properties']['gridY']
            office = data['properties']['gridId']
            forecast_url = data['properties']['forecast']
            forecast_grid_url = data['properties']['forecastGridData']
            return gridX, gridY, office, forecast_url, forecast_grid_url
        else:
            logger.error(f"Error: {response.status_code}, {response.text}")
            return None, None, None, None, None
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return None, None, None, None, None

# Function to get the grid forecast data, including QPF (precipitation amount)
def get_forecast_grid_data(forecast_grid_url):
    headers = {'User-Agent': 'YourAppName (youremail@example.com)'}
    try:
        response = requests.get(forecast_grid_url, headers=headers)
        if response.status_code == 200:
            forecast_data = response.json()
            qpf_values = forecast_data['properties']['quantitativePrecipitation']['values']
            qpf_df = pd.DataFrame([{
                'datetime': item['validTime'].split('/')[0],
                'qpf': item['value']
            } for item in qpf_values])
            return qpf_df
        else:
            logger.error(f"Error: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return None

# Function to get the forecast from the gridpoint
def get_forecast_by_gridpoint(gridX, gridY, office):
    url = f"https://api.weather.gov/gridpoints/{office}/{gridX},{gridY}/forecast"
    headers = {'User-Agent': 'YourAppName (youremail@example.com)'}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            forecast_data = response.json()
            periods = forecast_data['properties']['periods']
            forecast_df = pd.DataFrame([{
                'datetime': item['startTime'],
                'temperature': item['temperature'],
                'rain_forecast': 'rain' in item['detailedForecast'].lower(),
                'detailed_forecast': item['detailedForecast']
            } for item in periods])
            return forecast_df
        else:
            logger.error(f"Error: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return None

# Function to recommend irrigation
def recommend_irrigation(soil_moisture, crop_stage, rain_forecast, qpf, ndvi, cost_per_acre_inch):
    irrigation_needed = False
    water_in_inches = 0
    acre_inch_conversion = 102790.4

    crop_water_requirements = {
        'germination': 0.2,
        'vegetative': 0.3,
        'flowering': 0.4,
        'maturation': 0.2
    }

    ndvi_thresholds = {
        'germination': 0.3,
        'vegetative': 0.5,
        'flowering': 0.5,
        'maturation': 0.3
    }

    if soil_moisture < 30 and not rain_forecast:
        irrigation_needed = True
        water_in_inches = crop_water_requirements.get(crop_stage.lower(), 0.3)

    if rain_forecast and qpf > 0.2:
        irrigation_needed = False

    if ndvi is not None and ndvi < ndvi_thresholds.get(crop_stage.lower(), 0.5):
        irrigation_needed = True
        water_in_inches = max(water_in_inches, crop_water_requirements.get(crop_stage.lower(), 0.3))

    total_cost = water_in_inches * cost_per_acre_inch
    return irrigation_needed, water_in_inches, total_cost

# Function to create simulated data
def create_simulated_data():
    np.random.seed(42)
    sensor_ids = np.arange(1, 51)
    hybrids = np.random.choice(['Hybrid_A', 'Hybrid_B', 'Hybrid_C'], 50)
    field_locations = np.random.choice(['North', 'South', 'East', 'West'], 50)
    temperatures = np.random.uniform(15, 35, 50)
    humidities = np.random.uniform(30, 70, 50)
    water_usages = np.random.uniform(500, 2000, 50)

    optimal_water_usage = 1200
    yield_potential = 10

    yields = yield_potential * np.exp(-((water_usages - optimal_water_usage) ** 2) / (2 * (300 ** 2)))

    temp_optimal = 25
    humidity_optimal = 50
    temp_effect = np.exp(-((temperatures - temp_optimal) ** 2) / (2 * (5 ** 2)))
    humidity_effect = np.exp(-((humidities - humidity_optimal) ** 2) / (2 * (10 ** 2)))
    yields = yields * temp_effect * humidity_effect

    yields += np.random.normal(0, 0.5, 50)
    yields = np.clip(yields, 0, yield_potential)

    cost_per_gallon = np.random.uniform(0.05, 0.15, 50)

    data = {
        'Sensor_ID': sensor_ids,
        'Hybrid': hybrids,
        'Field_Location': field_locations,
        'Temperature': temperatures,
        'Humidity': humidities,
        'Water_Usage': water_usages,
        'Yield': yields,
        'Cost_per_Gallon': cost_per_gallon
    }
    return pd.DataFrame(data)

# Helper function to parse uploaded content
def parse_contents(contents, filename):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    try:
        if 'csv' in filename.lower():
            df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))
        elif 'xls' in filename.lower() or 'xlsx' in filename.lower():
            df = pd.read_excel(io.BytesIO(decoded))
        else:
            return None
    except Exception as e:
        logger.error(f"Error parsing file {filename}: {e}")
        return None
    return df

# ----------------------------- AGRICULTURAL DECISION SUPPORT DASHBOARD FUNCTIONS ----------------------------- #

# Function to load data for Agricultural Decision Support Dashboard
def load_ads_data():
    """
    Load processed CSV data generated by calculations.py.
    Assumes all CSV files are in the same directory as this script.
    """
    data_files = {
        'disease_risk_data': 'disease_risk_data.csv',
        'weather_data': 'weather_data.csv',
        'water_stress_data': 'water_stress_data.csv',
        'irrigation_data': 'irrigation_data.csv',
        'ec_profile': 'ec_profile.csv',
        'growth_stage_data': 'growth_stage_data.csv',
        'microclimate_data': 'microclimate_data.csv'
    }
    
    data = {}
    for key, file in data_files.items():
        try:
            if key == 'ec_profile':
                df = pd.read_csv(file)
            else:
                df = pd.read_csv(file, parse_dates=['Timestamp'])
            data[key] = df
            logger.debug(f"Loaded `{file}` successfully.")
        except FileNotFoundError:
            logger.error(f"File `{file}` not found. Please ensure it exists in the directory.")
            data[key] = pd.DataFrame()
        except pd.errors.ParserError as pe:
            logger.error(f"Error parsing `{file}`: {pe}")
            data[key] = pd.DataFrame()
        except Exception as e:
            logger.error(f"Unexpected error loading `{file}`: {e}")
            data[key] = pd.DataFrame()
    return data

# Load ADS data
ads_data = load_ads_data()

# Extract individual dataframes
disease_risk_data = ads_data.get('disease_risk_data', pd.DataFrame())
weather_data = ads_data.get('weather_data', pd.DataFrame())
water_stress_data = ads_data.get('water_stress_data', pd.DataFrame())
irrigation_data = ads_data.get('irrigation_data', pd.DataFrame())
ec_profile = ads_data.get('ec_profile', pd.DataFrame())
growth_stage_data = ads_data.get('growth_stage_data', pd.DataFrame())
microclimate_data = ads_data.get('microclimate_data', pd.DataFrame())

# ----------------------------- MAIN DASHBOARD LAYOUT ----------------------------- #

app.layout = html.Div(style={'backgroundColor': '#001f3f', 'minHeight': '100vh'}, children=[
    html.H1("PHIBRA MAX WATER",
            style={'color': '#FF4136', 'textAlign': 'center', 'fontFamily': 'tahoma',
                   'fontWeight': 'bold', 'fontSize': '68px', 'marginTop': '20px'}),

    dcc.Tabs(
        id='tabs-container',
        value='home',
        children=[
            dcc.Tab(
                label='HOME',
                value='home',
                className='custom-tab',
                selected_className='custom-tab--selected',
                style={
                    'fontSize': '20px',
                    'textTransform': 'uppercase',
                    'backgroundColor': '#228B22'
                }
            ),
            dcc.Tab(
                label='CERES.AI',
                value='ceresai',
                className='custom-tab',
                selected_className='custom-tab--selected',
                style={
                    'fontSize': '20px',
                    'textTransform': 'uppercase',
                    'backgroundColor': '#228B22'
                }
            ),
            dcc.Tab(
                label='AGRICULTURAL DECISION SUPPORT',
                value='ads',
                className='custom-tab',
                selected_className='custom-tab--selected',
                style={
                    'fontSize': '20px',
                    'textTransform': 'uppercase',
                    'backgroundColor': '#228B22'
                }
            ),
            dcc.Tab(
                label='WATER USE EFFICIENCY',
                value='water_use_efficiency',
                className='custom-tab',
                selected_className='custom-tab--selected',
                style={
                    'fontSize': '20px',
                    'textTransform': 'uppercase',
                    'backgroundColor': '#228B22'
                }
            ),
            dcc.Tab(
                label='IRRIGATION COST AND ANALYSIS',
                value='irrigation_cost_analysis',
                className='custom-tab',
                selected_className='custom-tab--selected',
                style={
                    'fontSize': '20px',
                    'textTransform': 'uppercase',
                    'backgroundColor': '#228B22'
                }
            ),
            dcc.Tab(
                label='ABOUT',
                value='about',
                className='custom-tab',
                selected_className='custom-tab--selected',
                style={
                    'fontSize': '20px',
                    'textTransform': 'uppercase',
                    'backgroundColor': '#228B22'
                }
            ),
        ],
        style={'backgroundColor': '#228B22'}
    ),

    html.Div(id='tab-content', style={'padding': '20px', 'color': '#FF4136', 'fontWeight': 'bold'})
])

# ----------------------------- TAB CONTENTS ----------------------------- #

# Render content based on selected tab
@app.callback(
    Output('tab-content', 'children'),
    [Input('tabs-container', 'value')]
)
def render_content(tab):
    if tab == 'home':
        home_children = [
            html.H2("WELCOME TO PHIBRA MAX WATER", style={'color': '#FF4136', 'textAlign': 'center'}),
            html.P("This platform provides tools for smart irrigation and agricultural decision support.",
                   style={'color': '#FF4136', 'textAlign': 'center'}),
        ]
        
        # Include image if available
        if encoded_image:
            home_children.append(
                html.Img(
                    src='data:image/jpeg;base64,{}'.format(encoded_image),
                    style={
                        'display': 'block',
                        'margin-left': 'auto',
                        'margin-right': 'auto',
                        'width': '50%',
                        'height': 'auto',
                        'marginTop': '20px'
                    }
                )
            )
        else:
            home_children.append(
                html.P("Image not available.", style={'color': 'red', 'textAlign': 'center'})
            )
        
        # Footer
        home_children.extend([
            html.Hr(style={'borderColor': '#FF4136'}),
            dbc.Row([
                dbc.Col([
                    html.P("© 2024 Agricultural Decision Support System PHIBRA MAX WATER | Developed by Lucas Batista and Menard Soni.",
                           className="text-center", style={'color': '#FF4136'})
                ])
            ])
        ])
        
        return html.Div(home_children)
    
    elif tab == 'ceresai':
        return html.Div([
            html.H2("CERES.AI INTEGRATION", style={'color': '#FF4136', 'textAlign': 'center', 'fontSize': '24px'}),
            html.Div(
                html.Iframe(
                    src="https://ceres.ai/",
                    style={"height": "800px", "width": "100%", "border": "none"}
                ),
                style={'marginTop': '20px'}
            ),
            # Footer
            html.Hr(style={'borderColor': '#FF4136'}),
            dbc.Row([
                dbc.Col([
                    html.P("© 2024 Agricultural Decision Support System PHIBRA MAX WATER | Developed by Lucas Batista and Menard Soni.",
                           className="text-center", style={'color': '#FF4136'})
                ])
            ])
        ])
    
    elif tab == 'ads':
        return dbc.Container([
            html.H1(" AGRICULTURAL DECISION SUPPORT ", className="text-center my-4", style={'color': '#FF4136'}),
            
            # Filters
            dbc.Row([
                dbc.Col([
                    html.H5("🔍 FILTERS", style={'color': '#FF4136'}),
                    # Date Range Picker
                    dbc.Label("Select Date Range", style={'color': '#FF4136'}),
                    dcc.DatePickerRange(
                        id='ads-date-range',
                        min_date_allowed=disease_risk_data['Timestamp'].min().date() if not disease_risk_data.empty else pd.to_datetime('today').date(),
                        max_date_allowed=disease_risk_data['Timestamp'].max().date() if not disease_risk_data.empty else pd.to_datetime('today').date(),
                        start_date=disease_risk_data['Timestamp'].min().date() if not disease_risk_data.empty else pd.to_datetime('today').date(),
                        end_date=disease_risk_data['Timestamp'].max().date() if not disease_risk_data.empty else pd.to_datetime('today').date()
                    ),
                    html.Br(),
                    # Disease Risk Level Selector
                    dbc.Label("Select Disease Risk Level", style={'color': '#FF4136'}),
                    dcc.Dropdown(
                        id='ads-risk-level',
                        options=[{'label': level, 'value': level} for level in disease_risk_data['Disease_Risk'].unique()] if not disease_risk_data.empty else [],
                        value=disease_risk_data['Disease_Risk'].unique().tolist() if not disease_risk_data.empty else [],
                        multi=True,
                        placeholder="Select risk levels"
                    ),
                ], md=4),
            ], className="mb-4"),
            
            # Key Metrics
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H5("Minimum Relative Humidity (%)", className="card-title"),
                            html.P(id='ads-mrh', className="card-text")
                        ])
                    ], color="info", inverse=True)
                ], md=4),
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H5("Mean Temperature (°F)", className="card-title"),
                            html.P(id='ads-mean-temp', className="card-text")
                        ])
                    ], color="warning", inverse=True)
                ], md=4),
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H5("Leaf Wetness (Hours)", className="card-title"),
                            html.P(id='ads-leaf-wetness', className="card-text")
                        ])
                    ], color="success", inverse=True)
                ], md=4),
            ], className="mb-4"),
            
            # Alerts
            dbc.Row([
                dbc.Col([
                    html.H4("🚨 ALERTS", style={'color': '#FF4136'}),
                    html.Div(id='ads-alerts')
                ])
            ], className="mb-4"),
            
            # Recommendations
            dbc.Row([
                dbc.Col([
                    html.H4("📝 RECOMMENDATIONS", style={'color': '#FF4136'}),
                    html.Ul(id='ads-recommendations')
                ])
            ], className="mb-4"),
            
            # Visualizations
            dbc.Row([
                dbc.Col([
                    html.H4("📈 DISEASE RISK DISTRIBUTION", style={'color': '#FF4136'}),
                    dcc.Graph(id='ads-disease-risk-distribution', config={'displayModeBar': False})
                ], md=6),
                dbc.Col([
                    html.H4("💧 WATER STRESS INDEX OVER TIME", style={'color': '#FF4136'}),
                    dcc.Graph(id='ads-water-stress-index', config={'displayModeBar': False})
                ], md=6),
            ], className="mb-4"),
            
            dbc.Row([
                dbc.Col([
                    html.H4("🚰 IRRIGATION REQUIREMENTS OVER TIME", style={'color': '#FF4136'}),
                    dcc.Graph(id='ads-irrigation-requirements', config={'displayModeBar': False})
                ], md=6),
                dbc.Col([
                    html.H4("🌱 SOIL HEALTH ASSESSMENT", style={'color': '#FF4136'}),
                    dcc.Graph(id='ads-soil-health', config={'displayModeBar': False})
                ], md=6),
            ], className="mb-4"),
            
            dbc.Row([
                dbc.Col([
                    html.H4("🌿 GROWTH STAGE MONITORING", style={'color': '#FF4136'}),
                    dcc.Graph(id='ads-growth-stage', config={'displayModeBar': False})
                ], md=6),
                dbc.Col([
                    html.H4("☀️ MICROCLIMATE ANALYSIS", style={'color': '#FF4136'}),
                    dcc.Graph(id='ads-microclimate', config={'displayModeBar': False})
                ], md=6),
            ], className="mb-4"),
            
            # Footer
            html.Hr(style={'borderColor': '#FF4136'}),
            dbc.Row([
                dbc.Col([
                    html.P("© 2024 Agricultural Decision Support System PHIBRA MAX WATER | Developed by Lucas Batista and Menard Soni.",
                           className="text-center", style={'color': '#FF4136'})
                ])
            ])
        ], fluid=True)
    
    elif tab == 'water_use_efficiency':
        return dbc.Container([
            dbc.Row([
                dbc.Col(html.H1(" WATER USE EFFICIENCY DASHBOARD",
                                className="text-center mb-4", style={'color': '#FF4136'}), width=12)
            ]),
            dbc.Row([
                dbc.Col([
                    html.Label("Upload your Sensor Data (.csv or .xlsx):", style={'color': '#FF4136'}),
                    dcc.Upload(
                        id='tab3-upload-sensor-data',
                        children=html.Div(['Drag and Drop or ', html.A('Select Files')]),
                        style={
                            'width': '100%', 'height': '50px', 'lineHeight': '50px',
                            'borderWidth': '1px', 'borderStyle': 'dashed',
                            'borderRadius': '5px', 'textAlign': 'center', 'margin-bottom': '10px',
                            'backgroundColor': '#f0f8ff',
                            'borderColor': '#007bff'
                        },
                        multiple=False
                    ),
                    html.Label("Upload your Hybrid Data (.csv or .xlsx):", style={'color': '#FF4136'}),
                    dcc.Upload(
                        id='tab3-upload-hybrid-data',
                        children=html.Div(['Drag and Drop or ', html.A('Select Files')]),
                        style={
                            'width': '100%', 'height': '50px', 'lineHeight': '50px',
                            'borderWidth': '1px', 'borderStyle': 'dashed',
                            'borderRadius': '5px', 'textAlign': 'center', 'margin-bottom': '10px',
                            'backgroundColor': '#f0f8ff',
                            'borderColor': '#007bff'
                        },
                        multiple=False
                    ),
                    html.Label("Enter Coordinates for Weather Forecast:", style={'color': '#FF4136'}),
                    dbc.Row([
                        dbc.Col([
                            html.Label("Latitude:", style={'color': '#FF4136'}),
                            dcc.Input(id='tab3-latitude-input', type='number',
                                      placeholder='Enter latitude', value=39.4, step=0.01,
                                      style={'width': '100%', 'margin-bottom': '10px'})
                        ], width=6),
                        dbc.Col([
                            html.Label("Longitude:", style={'color': '#FF4136'}),
                            dcc.Input(id='tab3-longitude-input', type='number',
                                      placeholder='Enter longitude', value=-101.05, step=0.01,
                                      style={'width': '100%', 'margin-bottom': '10px'})
                        ], width=6),
                    ]),
                    dbc.Row([
                        dbc.Col([
                            html.Button('Get Weather Forecast', id='tab3-get-weather-button', n_clicks=0,
                                        style={'backgroundColor': '#4CAF50', 'color': 'white', 'padding': '10px 20px',
                                               'border': 'none', 'cursor': 'pointer', 'width': '100%'})
                        ], width=6),
                        dbc.Col([
                            # Toggle button for Growth Stage Dropdown
                            dbc.Button("Toggle Growth Stage Selection", id="toggle-growth-stage", color="primary", className="mb-3", style={'width': '100%'})
                        ], width=6),
                    ]),
                    dbc.Collapse(
                        dbc.Form([
                            html.Label("Select Current Growth Stage:", style={'color': '#FF4136'}),
                            dcc.Dropdown(
                                id='tab3-growth-stage-dropdown',
                                options=[
                                    {'label': 'Germination', 'value': 'Germination'},
                                    {'label': 'Vegetative', 'value': 'Vegetative'},
                                    {'label': 'Flowering', 'value': 'Flowering'},
                                    {'label': 'Maturation', 'value': 'Maturation'}
                                ],
                                value='Vegetative',
                                clearable=False,
                                style={'width': '100%'}
                            ),
                        ]),
                        id="collapse-growth-stage",
                        is_open=False,
                    ),
                ], width=4),
                dbc.Col([
                    html.Div(id='tab3-output-data-upload', style={'margin-top': '10px'})
                ], width=8)
            ]),
            dbc.Row([
                dbc.Col([
                    dcc.Graph(id='tab3-moisture-sensor-plot', config={'displayModeBar': False})
                ], width=12)
            ]),
            dbc.Row([
                dbc.Col([
                    html.Div(id='tab3-moisture-table')
                ], width=12)
            ]),
            dbc.Row([
                dbc.Col([
                    dcc.Graph(id='tab3-rainfall-forecast-plot', config={'displayModeBar': False})
                ], width=12)
            ]),
            dbc.Row([
                dbc.Col([
                    dcc.Graph(id='tab3-water-use-efficiency-plot', config={'displayModeBar': False})
                ], width=12)
            ]),
            # Footer
            html.Hr(style={'borderColor': '#FF4136'}),
            dbc.Row([
                dbc.Col([
                    html.P("© 2024 Agricultural Decision Support System PHIBRA MAX WATER | Developed by Lucas Batista and Menard Soni.",
                           className="text-center", style={'color': '#FF4136'})
                ])
            ])
        ], fluid=True)
    
    elif tab == 'irrigation_cost_analysis':
        return dbc.Container([
            dbc.Row([
                dbc.Col(html.H1(" IRRIGATION COST AND ANALYSIS DASHBOARD", className="text-center mb-4", style={'color': '#FF4136'}), width=12)
            ]),
            dbc.Row([
                dbc.Col([
                    html.Label('Upload Planting Data CSV:', style={'color': '#FF4136'}),
                    dcc.Upload(
                        id='tab2-upload-planting-data',
                        children=html.Div([
                            'Drag and Drop or ',
                            html.A('Select Files')
                        ]),
                        style={
                            'width': '100%', 'height': '40px', 'lineHeight': '40px',
                            'borderWidth': '1px', 'borderStyle': 'dashed',
                            'borderRadius': '5px', 'textAlign': 'center', 'margin': '5px',
                            'backgroundColor': '#f0f8ff',
                            'borderColor': '#007bff'
                        },
                        multiple=False
                    ),
                    html.Div(id='tab2-planting-data-upload-status', style={'color': 'green', 'margin-bottom': '10px'}),
                ], width=3),
                dbc.Col([
                    html.Label('Upload Irrigation Data CSV:', style={'color': '#FF4136'}),
                    dcc.Upload(
                        id='tab2-upload-irrigation-data',
                        children=html.Div([
                            'Drag and Drop or ',
                            html.A('Select Files')
                        ]),
                        style={
                            'width': '100%', 'height': '40px', 'lineHeight': '40px',
                            'borderWidth': '1px', 'borderStyle': 'dashed',
                            'borderRadius': '5px', 'textAlign': 'center', 'margin': '5px',
                            'backgroundColor': '#f0f8ff',
                            'borderColor': '#007bff'
                        },
                        multiple=False
                    ),
                    html.Div(id='tab2-irrigation-data-upload-status', style={'color': 'green', 'margin-bottom': '10px'}),
                ], width=3),
                dbc.Col([
                    html.Label('Upload Fertilizer Data CSV:', style={'color': '#FF4136'}),
                    dcc.Upload(
                        id='tab2-upload-fertilizer-data',
                        children=html.Div([
                            'Drag and Drop or ',
                            html.A('Select Files')
                        ]),
                        style={
                            'width': '100%', 'height': '40px', 'lineHeight': '40px',
                            'borderWidth': '1px', 'borderStyle': 'dashed',
                            'borderRadius': '5px', 'textAlign': 'center', 'margin': '5px',
                            'backgroundColor': '#f0f8ff',
                            'borderColor': '#007bff'
                        },
                        multiple=False
                    ),
                    html.Div(id='tab2-fertilizer-data-upload-status', style={'color': 'green', 'margin-bottom': '10px'}),
                ], width=3),
                dbc.Col([
                    # Toggle button for Select Corn Hybrid Dropdown
                    dbc.Button("Toggle Hybrid Selection", id="toggle-hybrid-dropdown", color="primary", className="mb-3", style={'width': '100%'}),
                    dbc.Collapse(
                        dcc.Dropdown(id='tab2-hybrid-dropdown', multi=True, placeholder="Select Hybrids",
                                     style={'margin-bottom': '10px'}),
                        id="collapse-hybrid-dropdown",
                        is_open=False,
                    ),
                ], width=3),
            ]),
            dbc.Row([
                dbc.Col([
                    html.Label('Adjust Price per Irrigation (USD):', style={'color': '#FF4136'}),
                    dcc.Input(id='tab2-price-input-irrigation', type='number', value=15, step=0.5, min=0,
                              style={'width': '100%', 'margin-bottom': '10px'})
                ], width=4),
                dbc.Col([
                    html.Label('Adjust Price per Fertilizer Application (USD):', style={'color': '#FF4136'}),
                    dcc.Input(id='tab2-price-input-fertilizer', type='number', value=0.5, step=0.1, min=0,
                              style={'width': '100%', 'margin-bottom': '10px'})
                ], width=4),
                dbc.Col([
                    html.Label('Select Date Range for Analysis:', style={'color': '#FF4136'}),
                    dcc.DatePickerRange(
                        id='tab2-irrigation-date-picker',
                        start_date=datetime.date.today() - datetime.timedelta(days=30),
                        end_date=datetime.date.today(),
                        display_format='YYYY-MM-DD',
                        start_date_placeholder_text='Start Date',
                        end_date_placeholder_text='End Date',
                        style={'width': '100%', 'margin-bottom': '10px'}
                    )
                ], width=4),
            ]),
            dbc.Row([
                dbc.Col([
                    dcc.Loading(
                        id="tab2-loading-1",
                        type="default",
                        children=dcc.Graph(id='tab2-irrigation-cost-graph', config={'displayModeBar': False})
                    )
                ], width=12)
            ]),
            dbc.Row([
                dbc.Col([
                    dcc.Loading(
                        id="tab2-loading-2",
                        type="default",
                        children=dcc.Graph(id='tab2-fertilizer-cost-graph', config={'displayModeBar': False})
                    )
                ], width=12)
            ]),
            dbc.Row([
                dbc.Col([
                    dcc.Loading(
                        id="tab2-loading-3",
                        type="default",
                        children=dcc.Graph(id='tab2-total-cost-graph', config={'displayModeBar': False})
                    )
                ], width=12)
            ]),
            # Total Cost per Hybrid Section
            dbc.Row([
                dbc.Col([
                    html.H4(" TOTAL COST PER HYBRID", style={'color': '#FF4136', 'textAlign': 'center'}),
                    dcc.Graph(id='tab2-total-cost-per-hybrid-graph', config={'displayModeBar': False})
                ], width=12)
            ], className="mb-4"),
            # Footer
            html.Hr(style={'borderColor': '#FF4136'}),
            dbc.Row([
                dbc.Col([
                    html.P("© 2024 Agricultural Decision Support System PHIBRA MAX WATER | Developed by Lucas Batista and Menard Soni.",
                           className="text-center", style={'color': '#FF4136'})
                ])
            ])
        ], fluid=True)
    
    elif tab == 'about':
        return dbc.Container([
            html.H2("ABOUT", style={'color': '#FF4136', 'textAlign': 'center'}),
            html.P("Developed by Lucas Batista and Menard Soni.",
                   style={'color': '#FF4136', 'textAlign': 'center', 'fontSize': '24px'}),
            html.P("PHIBRA MAX WATER integrates advanced agricultural decision support tools to enhance water use efficiency and optimize irrigation strategies. By leveraging real-time data and predictive analytics, farmers can make informed decisions to improve crop yields and reduce costs.",
                   style={'color': '#FF4136', 'textAlign': 'center', 'fontSize': '18px'}),
            html.P("Contact: lab93@ksu.edu / masoni@ksu.edu",
                   style={'color': '#FF4136', 'textAlign': 'center', 'fontSize': '18px'}),
            html.Div(
                html.A("Visit CeresAI for more information.",
                       href="https://ceres.ai/", target="_blank",
                       style={'color': '#FF4136', 'fontSize': '18px'})
            ),
            # Footer
            html.Hr(style={'borderColor': '#FF4136'}),
            dbc.Row([
                dbc.Col([
                    html.P("© 2024 Agricultural Decision Support System PHIBRA MAX WATER | Developed by Lucas Batista and Menard Soni.",
                           className="text-center", style={'color': '#FF4136'})
                ])
            ])
        ], fluid=True)
    
    else:
        return html.Div(f"Content for {tab} will be here.", style={'color': '#FF4136'})

# ----------------------------- CALLBACKS ----------------------------- #

# ----------------------------- AGRICULTURAL DECISION SUPPORT DASHBOARD CALLBACKS ----------------------------- #

# Callback to update key metrics in ADS
@app.callback(
    [Output('ads-mrh', 'children'),
     Output('ads-mean-temp', 'children'),
     Output('ads-leaf-wetness', 'children')],
    [Input('ads-date-range', 'start_date'),
     Input('ads-date-range', 'end_date'),
     Input('ads-risk-level', 'value')]
)
def update_ads_metrics(start_date, end_date, selected_risk):
    if not disease_risk_data.empty:
        mask = (
            (disease_risk_data['Timestamp'].dt.date >= pd.to_datetime(start_date).date()) &
            (disease_risk_data['Timestamp'].dt.date <= pd.to_datetime(end_date).date())
        )
        if selected_risk:
            mask &= disease_risk_data['Disease_Risk'].isin(selected_risk)
        filtered = disease_risk_data[mask]
        if not filtered.empty:
            latest_entry = filtered.iloc[-1]
            mrh = latest_entry.get('Minimum_Relative_Humidity', 'N/A')
            temp = latest_entry.get('Mean_Temp', 'N/A')
            leaf_wetness = latest_entry.get('Leaf_Wetness_Hours', 'N/A')
            return f"{mrh}%", f"{temp}°F", f"{leaf_wetness} hrs"
    return "N/A", "N/A", "N/A"

# Callback to update alerts in ADS
@app.callback(
    Output('ads-alerts', 'children'),
    [Input('ads-date-range', 'start_date'),
     Input('ads-date-range', 'end_date'),
     Input('ads-risk-level', 'value')]
)
def update_ads_alerts(start_date, end_date, selected_risk):
    if not disease_risk_data.empty:
        mask = (
            (disease_risk_data['Timestamp'].dt.date >= pd.to_datetime(start_date).date()) &
            (disease_risk_data['Timestamp'].dt.date <= pd.to_datetime(end_date).date())
        )
        if selected_risk:
            mask &= disease_risk_data['Disease_Risk'].isin(selected_risk)
        filtered = disease_risk_data[mask]
        if not filtered.empty:
            latest_entry = filtered.iloc[-1]
            risk_level = latest_entry.get('Disease_Risk', 'N/A')
            if risk_level == 'High Risk':
                return dbc.Alert("**High Risk Conditions Detected!** Immediate action recommended.", color="danger")
            elif risk_level == 'Moderate Risk':
                return dbc.Alert("**Moderate Risk Conditions.** Monitor closely and prepare for possible intervention.", color="warning")
            else:
                return dbc.Alert("**Low Risk Conditions.** Continue regular practices.", color="success")
    return "No data available."

# Callback to update recommendations in ADS
@app.callback(
    Output('ads-recommendations', 'children'),
    [Input('ads-date-range', 'start_date'),
     Input('ads-date-range', 'end_date'),
     Input('ads-risk-level', 'value')]
)
def update_ads_recommendations(start_date, end_date, selected_risk):
    if not disease_risk_data.empty:
        mask = (
            (disease_risk_data['Timestamp'].dt.date >= pd.to_datetime(start_date).date()) &
            (disease_risk_data['Timestamp'].dt.date <= pd.to_datetime(end_date).date())
        )
        if selected_risk:
            mask &= disease_risk_data['Disease_Risk'].isin(selected_risk)
        filtered = disease_risk_data[mask]
        if not filtered.empty:
            latest_entry = filtered.iloc[-1]
            risk_level = latest_entry.get('Disease_Risk', 'N/A')
            if risk_level == 'High Risk':
                recommendations = [
                    "Apply fungicides as a preventive measure.",
                    "Increase monitoring for early detection of disease symptoms.",
                    "Ensure proper irrigation to maintain optimal soil moisture."
                ]
            elif risk_level == 'Moderate Risk':
                recommendations = [
                    "Monitor crop health regularly.",
                    "Prepare treatment plans in case conditions worsen.",
                    "Maintain adequate irrigation to reduce plant stress."
                ]
            else:
                recommendations = [
                    "Continue regular farming practices.",
                    "Monitor weather forecasts for any changes in conditions."
                ]
            return [html.Li(rec) for rec in recommendations]
    return [html.Li("No recommendations available. Please adjust your filters.")]

# Callback to update Disease Risk Distribution in ADS
@app.callback(
    Output('ads-disease-risk-distribution', 'figure'),
    [Input('ads-date-range', 'start_date'),
     Input('ads-date-range', 'end_date'),
     Input('ads-risk-level', 'value')]
)
def update_ads_disease_risk_distribution(start_date, end_date, selected_risk):
    if not disease_risk_data.empty:
        mask = (
            (disease_risk_data['Timestamp'].dt.date >= pd.to_datetime(start_date).date()) &
            (disease_risk_data['Timestamp'].dt.date <= pd.to_datetime(end_date).date())
        )
        if selected_risk:
            mask &= disease_risk_data['Disease_Risk'].isin(selected_risk)
        filtered = disease_risk_data[mask]
        if not filtered.empty:
            fig = px.histogram(
                filtered,
                x='Disease_Risk',
                title="Disease Risk Distribution",
                labels={'Disease_Risk': 'Risk Level', 'count': 'Number of Instances'},
                color='Disease_Risk',
                color_discrete_map={'Low Risk': 'green', 'Moderate Risk': 'orange', 'High Risk': 'red'},
                template='plotly_dark'
            )
            return fig
    # Return empty figure with message
    fig = go.Figure()
    fig.update_layout(
        title="Disease Risk Distribution",
        xaxis_title="Risk Level",
        yaxis_title="Number of Instances",
        template='plotly_dark',
        annotations=[
            dict(
                text="No data available for the selected filters.",
                xref="paper", yref="paper",
                showarrow=False,
                font=dict(size=20, color='white')
            )
        ]
    )
    return fig

# Callback to update Water Stress Index Over Time in ADS
@app.callback(
    Output('ads-water-stress-index', 'figure'),
    [Input('ads-date-range', 'start_date'),
     Input('ads-date-range', 'end_date')]
)
def update_ads_water_stress(start_date, end_date):
    if not water_stress_data.empty:
        mask = (
            (water_stress_data['Timestamp'].dt.date >= pd.to_datetime(start_date).date()) &
            (water_stress_data['Timestamp'].dt.date <= pd.to_datetime(end_date).date())
        )
        filtered = water_stress_data[mask]
        if not filtered.empty:
            fig = px.line(
                filtered,
                x='Timestamp',
                y='Water_Stress_Index',
                title="Water Stress Index Over Time",
                labels={'Timestamp': 'Date', 'Water_Stress_Index': 'Water Stress Index'},
                markers=True,
                template='plotly_dark',
                color='Hybrid' if 'Hybrid' in filtered.columns else None
            )
            return fig
    # Return empty figure with message
    fig = go.Figure()
    fig.update_layout(
        title="Water Stress Index Over Time",
        xaxis_title="Date",
        yaxis_title="Water Stress Index",
        template='plotly_dark',
        annotations=[
            dict(
                text="No Water Stress data available for the selected date range.",
                xref="paper", yref="paper",
                showarrow=False,
                font=dict(size=20, color='white')
            )
        ]
    )
    return fig

# Callback to update Irrigation Requirements Over Time in ADS
@app.callback(
    Output('ads-irrigation-requirements', 'figure'),
    [Input('ads-date-range', 'start_date'),
     Input('ads-date-range', 'end_date')]
)
def update_ads_irrigation_requirements(start_date, end_date):
    if not irrigation_data.empty:
        mask = (
            (irrigation_data['Timestamp'].dt.date >= pd.to_datetime(start_date).date()) &
            (irrigation_data['Timestamp'].dt.date <= pd.to_datetime(end_date).date())
        )
        filtered = irrigation_data[mask]
        if not filtered.empty:
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(
                go.Scatter(
                    x=filtered['Timestamp'],
                    y=filtered['Gross_Irrigation_Requirement_mm'],
                    mode='lines+markers',
                    name='Gross Irrigation',
                    line=dict(color='green')
                ),
                secondary_y=False,
            )
            fig.add_trace(
                go.Scatter(
                    x=filtered['Timestamp'],
                    y=filtered['Net_Irrigation_Requirement_mm'],
                    mode='lines+markers',
                    name='Net Irrigation',
                    line=dict(color='blue')
                ),
                secondary_y=False,
            )
            fig.update_layout(
                title="Irrigation Requirements Over Time",
                xaxis_title="Date",
                yaxis_title="Irrigation Requirement (mm)",
                legend_title="Irrigation Type",
                template='plotly_dark',
                hovermode='x unified'
            )
            return fig
    # Return empty figure with message
    fig = go.Figure()
    fig.update_layout(
        title="Irrigation Requirements Over Time",
        xaxis_title="Date",
        yaxis_title="Irrigation Requirement (mm)",
        template='plotly_dark',
        annotations=[
            dict(
                text="No Irrigation data available for the selected date range.",
                xref="paper", yref="paper",
                showarrow=False,
                font=dict(size=20, color='white')
            )
        ]
    )
    return fig

# Callback to update Soil Health Assessment in ADS
@app.callback(
    Output('ads-soil-health', 'figure'),
    [Input('ads-date-range', 'start_date'),
     Input('ads-date-range', 'end_date')]
)
def update_ads_soil_health(start_date, end_date):
    if not ec_profile.empty:
        # Assuming EC does not change over time, but filtered by date range if applicable
        # If EC is time-dependent, apply similar filtering
        fig = px.bar(
            ec_profile,
            x='Depth',
            y='EC',
            title="Electrical Conductivity (EC) Profile by Depth",
            labels={'Depth': 'Depth', 'EC': 'Electrical Conductivity (dS/m)'},
            color='EC',
            color_continuous_scale='Viridis',
            template='plotly_dark'
        )
        return fig
    # Return empty figure with message
    fig = go.Figure()
    fig.update_layout(
        title="Soil Health Assessment",
        xaxis_title="Depth",
        yaxis_title="Electrical Conductivity (dS/m)",
        template='plotly_dark',
        annotations=[
            dict(
                text="Soil Health data not available.",
                xref="paper", yref="paper",
                showarrow=False,
                font=dict(size=20, color='white')
            )
        ]
    )
    return fig

# Callback to update Growth Stage Monitoring in ADS
@app.callback(
    Output('ads-growth-stage', 'figure'),
    [Input('ads-date-range', 'start_date'),
     Input('ads-date-range', 'end_date')]
)
def update_ads_growth_stage(start_date, end_date):
    if not growth_stage_data.empty:
        mask = (
            (growth_stage_data['Timestamp'].dt.date >= pd.to_datetime(start_date).date()) &
            (growth_stage_data['Timestamp'].dt.date <= pd.to_datetime(end_date).date())
        )
        filtered = growth_stage_data[mask]
        if not filtered.empty:
            fig = px.line(
                filtered,
                x='Timestamp',
                y='Accumulated_GDD',
                title="Accumulated Growing Degree Days (GDD) Over Time",
                labels={'Timestamp': 'Date', 'Accumulated_GDD': 'Accumulated GDD'},
                markers=True,
                template='plotly_dark'
            )
            return fig
    # Return empty figure with message
    fig = go.Figure()
    fig.update_layout(
        title="Growth Stage Monitoring",
        xaxis_title="Date",
        yaxis_title="Accumulated GDD",
        template='plotly_dark',
        annotations=[
            dict(
                text="Growth Stage data not available for the selected date range.",
                xref="paper", yref="paper",
                showarrow=False,
                font=dict(size=20, color='white')
            )
        ]
    )
    return fig

# Callback to update Microclimate Analysis in ADS
@app.callback(
    Output('ads-microclimate', 'figure'),
    [Input('ads-date-range', 'start_date'),
     Input('ads-date-range', 'end_date')]
)
def update_ads_microclimate(start_date, end_date):
    if not microclimate_data.empty:
        mask = (
            (microclimate_data['Timestamp'].dt.date >= pd.to_datetime(start_date).date()) &
            (microclimate_data['Timestamp'].dt.date <= pd.to_datetime(end_date).date())
        )
        filtered = microclimate_data[mask]
        if not filtered.empty:
            # Check if 'Microclimate_Zone' exists, else categorize
            if 'Microclimate_Zone' not in filtered.columns:
                def categorize_microclimate(row):
                    if row['Mean_Temp'] > 30 and row['Minimum_Relative_Humidity'] < 40:
                        return 'Hot & Dry'
                    elif row['Mean_Temp'] <= 30 and row['Minimum_Relative_Humidity'] >= 40:
                        return 'Cool & Humid'
                    else:
                        return 'Moderate'
                filtered['Microclimate_Zone'] = filtered.apply(categorize_microclimate, axis=1)
            
            fig = px.scatter(
                filtered,
                x='Mean_Temp',
                y='Minimum_Relative_Humidity',
                color='Microclimate_Zone',
                size='Wind_Speed',
                hover_data=['Timestamp', 'Recommendations'],
                title="Microclimate Parameters",
                labels={'Mean_Temp': 'Temperature (°F)', 'Minimum_Relative_Humidity': 'Humidity (%)'},
                template='plotly_dark'
            )
            return fig
    # Return empty figure with message
    fig = go.Figure()
    fig.update_layout(
        title="Microclimate Analysis",
        xaxis_title="Mean Temperature (°F)",
        yaxis_title="Minimum Relative Humidity (%)",
        template='plotly_dark',
        annotations=[
            dict(
                text="Microclimate data not available for the selected date range.",
                xref="paper", yref="paper",
                showarrow=False,
                font=dict(size=20, color='white')
            )
        ]
    )
    return fig

# ----------------------------- WATER USE EFFICIENCY DASHBOARD CALLBACKS ----------------------------- #

# Callback for updating tab3 outputs
@app.callback(
    [
        Output('tab3-output-data-upload', 'children'),
        Output('tab3-water-use-efficiency-plot', 'figure'),
        Output('tab3-moisture-sensor-plot', 'figure'),
        Output('tab3-moisture-table', 'children'),
        Output('tab3-rainfall-forecast-plot', 'figure')
    ],
    [
        Input('tab3-upload-sensor-data', 'contents'),
        Input('tab3-upload-sensor-data', 'filename'),
        Input('tab3-upload-hybrid-data', 'contents'),
        Input('tab3-upload-hybrid-data', 'filename'),
        Input('tab3-get-weather-button', 'n_clicks'),
        Input('tab3-growth-stage-dropdown', 'value')
    ],
    [
        State('tab3-latitude-input', 'value'),
        State('tab3-longitude-input', 'value')
    ]
)
def update_tab3_output(sensor_contents, sensor_filename, hybrid_contents,
                       hybrid_filename, n_clicks, growth_stage, latitude, longitude):
    # Use simulated data
    data = create_simulated_data()

    # Handle uploaded sensor data
    if sensor_contents:
        sensor_df = parse_contents(sensor_contents, sensor_filename)
        if sensor_df is not None:
            required_columns = ['Sensor_ID', 'Date', 'Depth', 'Moisture_Level']
            missing_columns = [col for col in required_columns if col not in sensor_df.columns]
            if missing_columns:
                upload_message = f"Error: Missing columns in sensor data: {', '.join(missing_columns)}"
                return html.Div(upload_message), go.Figure(), go.Figure(), html.Div(), go.Figure()
            if 'Sensor_Type' not in sensor_df.columns:
                sensor_df['Sensor_Type'] = 'Unknown'
            sensor_df['Date'] = pd.to_datetime(sensor_df['Date'], errors='coerce')
            if sensor_df['Date'].isnull().any():
                upload_message = "Error: Invalid date format in sensor data."
                return html.Div(upload_message), go.Figure(), go.Figure(), html.Div(), go.Figure()
            moisture_df = sensor_df
            upload_status = html.Span("Sensor data uploaded successfully!", style={'color': 'green'})
        else:
            upload_message = "Error: Could not parse sensor data file."
            return html.Div(upload_message), go.Figure(), go.Figure(), html.Div(), go.Figure()
    else:
        dates = pd.date_range(start=datetime.datetime.now() - datetime.timedelta(days=29), periods=30).tolist()
        depths = np.arange(3, 65, 5)
        moisture_data = {
            'Date': np.tile(dates, len(depths) * len(data['Sensor_ID'].unique())),
            'Depth': np.tile(np.repeat(depths, len(dates)), len(data['Sensor_ID'].unique())),
            'Sensor_ID': np.repeat(data['Sensor_ID'].unique(), len(depths) * len(dates)),
            'Moisture_Level': np.random.uniform(10, 50, len(dates) * len(depths) * len(data['Sensor_ID'].unique())),
            'Sensor_Type': 'Simulated'
        }
        moisture_df = pd.DataFrame(moisture_data)
        upload_status = html.Span("Using simulated sensor data.", style={'color': 'blue'})
    
    # Handle uploaded hybrid data
    if hybrid_contents:
        hybrid_df = parse_contents(hybrid_contents, hybrid_filename)
        if hybrid_df is not None:
            # Assuming hybrid data has 'Sensor_ID' and 'CompanyHybrid' columns
            if 'Sensor_ID' not in hybrid_df.columns or 'CompanyHybrid' not in hybrid_df.columns:
                upload_message = "Error: Missing 'Sensor_ID' or 'CompanyHybrid' columns in hybrid data."
                return html.Div(upload_message), go.Figure(), go.Figure(), html.Div(), go.Figure()
            data = data.merge(hybrid_df, on='Sensor_ID', how='left')
            upload_status = html.Span("Hybrid data uploaded successfully!", style={'color': 'green'})
        else:
            upload_message = "Error: Could not parse hybrid data file."
            return html.Div(upload_message), go.Figure(), go.Figure(), html.Div(), go.Figure()
    
    # Handle weather data
    if n_clicks > 0:
        if latitude is not None and longitude is not None:
            # Placeholder for actual weather forecast fetching function
            # Replace `get_forecast_by_gridpoint` with the actual function if available
            gridX, gridY, office, forecast_url, forecast_grid_url = get_gridpoint_by_coords(latitude, longitude)
            if gridX is not None and gridY is not None and office is not None:
                forecast_df = get_forecast_by_gridpoint(gridX, gridY, office)
                if forecast_df is not None:
                    qpf_df = get_forecast_grid_data(forecast_grid_url)
                    if qpf_df is not None:
                        rain_forecast = any(forecast_df['rain_forecast'])
                        qpf = qpf_df['qpf'].mean()
                    else:
                        rain_forecast = False
                        qpf = 0
                else:
                    forecast_df = pd.DataFrame()
                    rain_forecast = False
                    qpf = 0
            else:
                forecast_df = pd.DataFrame()
                rain_forecast = False
                qpf = 0
        else:
            forecast_df = pd.DataFrame()
            rain_forecast = False
            qpf = 0
    else:
        forecast_dates = pd.date_range(start=datetime.datetime.now(), periods=7).tolist()
        rainfall_forecast = np.random.uniform(0, 20, len(forecast_dates))
        pop_forecast = np.random.uniform(0, 100, len(forecast_dates))
        forecast_df = pd.DataFrame({
            'Date': forecast_dates,
            'Rainfall_Forecast': rainfall_forecast / 25.4,  # Convert mm to inches
            'Probability_of_Precipitation': pop_forecast
        })
        rain_forecast = any(forecast_df['Rainfall_Forecast'] > 0)
        qpf = forecast_df['Rainfall_Forecast'].mean()
    
    data['Total_Water_Cost'] = data['Water_Usage'] * data['Cost_per_Gallon']
    market_price_per_unit = 2.0
    data['Gross_Revenue'] = data['Yield'] * market_price_per_unit
    data['EWUE'] = (100*(data['Gross_Revenue'] - data['Total_Water_Cost']) / data['Water_Usage'])
    baseline_yield = 2.0
    data['IWUE'] = (100*(data['Yield'] - baseline_yield) / data['Water_Usage'])

    # Economic WUE vs Total Cost and Irrigation WUE vs Water Usage with Legends per Hybrid
    
    # Economic WUE vs Total Cost and Irrigation WUE vs Water Usage with Legends per Hybrid
    if 'Hybrid' in data.columns:
        fig1 = make_subplots(rows=1, cols=2,
                             subplot_titles=('Economic WUE vs Total Cost', 'Irrigation WUE vs Water Usage'))
        hybrids = data['Hybrid'].unique()
        for hybrid in hybrids:
            hybrid_data = data[data['Hybrid'] == hybrid]
            fig1.add_trace(
                go.Scatter(
                    x=hybrid_data['Total_Water_Cost'],
                    y=hybrid_data['EWUE'],
                    mode='markers',
                    marker=dict(
                        size=10,
                        symbol='circle',
                        opacity=0.8
                    ),
                    name=f'EWUE - {hybrid}',
                    text=hybrid_data['Hybrid'],
                    hovertemplate='Hybrid: %{text}<br>Total Cost: $%{x:.2f}<br>EWUE: %{y:.4f}'
                ),
                row=1, col=1
            )
            fig1.add_trace(
                go.Scatter(
                    x=hybrid_data['Water_Usage'],
                    y=hybrid_data['IWUE'],
                    mode='markers',
                    marker=dict(
                        size=10,
                        symbol='square',
                        opacity=0.8
                    ),
                    name=f'IWUE - {hybrid}',
                    text=hybrid_data['Hybrid'],
                    hovertemplate='Hybrid: %{text}<br>Water Usage: %{x:.2f}<br>IWUE: %{y:.4f}'
                ),
                row=1, col=2
            )

        fig1.update_layout(
            title='Water Use Efficiency Metrics',
            template='plotly_dark',
            showlegend=True
        )

    else:
        fig1 = go.Figure()
        fig1.update_layout(
            title='Water Use Efficiency Metrics',
            template='plotly_dark',
            annotations=[
                dict(
                    text="No Hybrid data available.",
                    xref="paper", yref="paper",
                    showarrow=False,
                    font=dict(size=20, color='white')
                )
            ]
        )
    
    # Soil Moisture Heatmap
    moisture_df = moisture_df.sort_values(['Depth', 'Date'])
    moisture_df['Date_str'] = moisture_df['Date'].dt.strftime('%Y-%m-%d')

    recent_dates = moisture_df['Date'].dt.date.unique()[-15:]
    filtered_moisture_df = moisture_df[moisture_df['Date'].dt.date.isin(recent_dates)]

    moisture_pivot = filtered_moisture_df.pivot_table(
        index='Depth',
        columns='Date_str',
        values='Moisture_Level',
        aggfunc='mean'
    )

    fig_moisture = go.Figure(data=go.Heatmap(
        z=moisture_pivot.values,
        x=moisture_pivot.columns,
        y=moisture_pivot.index,
        colorscale='Blues',
        colorbar=dict(title='Soil Moisture (%)')
    ))

    fig_moisture.update_layout(
        title='Recent Soil Moisture Levels Over Depth',
        xaxis_title='Date',
        yaxis_title='Depth (inches)',
        template='plotly_dark'
    )

    # Moisture Table
    moisture_table = html.Div([
        dbc.Table.from_dataframe(filtered_moisture_df[['Sensor_ID', 'Date_str', 'Depth', 'Moisture_Level', 'Sensor_Type']],
                                 striped=True, bordered=True, hover=True, responsive=True),
    ], style={'height': '300px', 'overflowY': 'scroll', 'backgroundColor': '#001f3f', 'color': 'white', 'textAlign': 'center'})

    # Rainfall Forecast and Irrigation Threshold in Inches
    if not forecast_df.empty:
        forecast_df['Cumulative_Rainfall'] = forecast_df['Rainfall_Forecast'].cumsum()
    else:
        forecast_df = pd.DataFrame({
            'Date': [],
            'Rainfall_Forecast': [],
            'Probability_of_Precipitation': [],
            'Cumulative_Rainfall': []
        })
    
    # Growth Stages
    growth_stages = {
        'germination': {'soil_capacity': 1.18},  # 30 mm / 25.4 = 1.18 inches
        'vegetative': {'soil_capacity': 1.57},   # 40 mm / 25.4 = 1.57 inches
        'flowering': {'soil_capacity': 1.97},    # 50 mm / 25.4 = 1.97 inches
        'maturation': {'soil_capacity': 1.38}    # 35 mm / 25.4 = 1.38 inches
    }

    current_stage = growth_stage.lower() if isinstance(growth_stage, str) else 'vegetative'
    current_soil_capacity = growth_stages.get(current_stage, {}).get('soil_capacity', 0.79)  # Default to 20 mm / 25.4

    if not moisture_df.empty:
        latest_moisture_date = moisture_df['Date'].max()
        recent_moisture = moisture_df[moisture_df['Date'] == latest_moisture_date]
        average_soil_moisture = recent_moisture['Moisture_Level'].mean() / 25.4  # Convert mm to inches
    else:
        average_soil_moisture = 0

    total_forecasted_rain = forecast_df['Rainfall_Forecast'].sum() if not forecast_df.empty else 0
    total_available_water = average_soil_moisture + total_forecasted_rain

    irrigation_threshold = current_soil_capacity - total_available_water
    irrigation_threshold = max(irrigation_threshold, 0)

    if not forecast_df.empty:
        forecast_df['Total_Available_Water'] = average_soil_moisture + forecast_df['Cumulative_Rainfall']
    else:
        forecast_df['Total_Available_Water'] = []

    fig_forecast = make_subplots(specs=[[{"secondary_y": True}]])
    if not forecast_df.empty:
        fig_forecast.add_trace(
            go.Bar(
                x=forecast_df['Date'],
                y=forecast_df['Rainfall_Forecast'],
                name='Rainfall Forecast (in)',
                marker_color='skyblue'
            ),
            secondary_y=False,
        )

        fig_forecast.add_trace(
            go.Scatter(
                x=forecast_df['Date'],
                y=forecast_df['Cumulative_Rainfall'],
                name='Cumulative Rainfall (in)',
                mode='lines+markers',
                marker_color='blue'
            ),
            secondary_y=True,
        )

        fig_forecast.add_trace(
            go.Scatter(
                x=forecast_df['Date'],
                y=forecast_df['Total_Available_Water'],
                name='Total Available Water (in)',
                mode='lines+markers',
                marker_color='green'
            ),
            secondary_y=True,
        )

    fig_forecast.add_hline(y=current_soil_capacity, line_dash='dash', line_color='red', yref='y2',
                           annotation_text=f'Soil Capacity for {current_stage.capitalize()}', annotation_position='top right')

    fig_forecast.update_layout(
        title='Rainfall Forecast and Irrigation Threshold',
        xaxis_title='Date',
        template='plotly_dark',
        legend=dict(
            x=0.01,
            y=0.99,
            bgcolor='rgba(0,0,0,0)'
        )
    )

    fig_forecast.update_yaxes(title_text="Daily Rainfall (in)", secondary_y=False)
    fig_forecast.update_yaxes(title_text="Cumulative/Total Water (in)", secondary_y=True)

    # Water Use Efficiency Plot
    fig_wue = fig1

    # Update fig_wue to include the second plot
   

    # Moisture Sensor Plot (Heatmap)
    # Already defined as fig_moisture above

    # Rainfall Forecast Plot
    # Already defined as fig_forecast above

    # Update plots if needed
    # ...

    return upload_status, fig_wue , fig_moisture, moisture_table, fig_forecast

# ----------------------------- IRRIGATION COST AND ANALYSIS CALLBACKS ----------------------------- #

# Callback to handle planting data upload and update hybrid dropdown
@app.callback(
    [Output('tab2-hybrid-dropdown', 'options'),
     Output('tab2-hybrid-dropdown', 'value'),
     Output('tab2-planting-data-upload-status', 'children')],
    [Input('tab2-upload-planting-data', 'contents')],
    [State('tab2-upload-planting-data', 'filename')]
)
def update_planting_data(planting_contents, planting_filename):
    if planting_contents is not None:
        df = parse_contents(planting_contents, planting_filename)
        if df is not None:
            # Check for required columns
            required_columns = ['FarmID', 'PlantingDate', 'CompanyHybrid', 'Seeding Rate(plants/ac)']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                upload_status = html.Span(f"Error: Missing columns in planting data: {', '.join(missing_columns)}", style={'color': 'red'})
                return [], None, upload_status
            hybrid_options = [{'label': hybrid, 'value': hybrid} for hybrid in df['CompanyHybrid'].unique()]
            upload_status = html.Span("Planting data uploaded successfully!", style={'color': 'green'})
            return hybrid_options, df['CompanyHybrid'].unique().tolist(), upload_status
        else:
            upload_status = html.Span("Error: Could not parse planting data file.", style={'color': 'red'})
            return [], None, upload_status
    return [], None, ""

# Callback to toggle the Hybrid Dropdown
@app.callback(
    Output("collapse-hybrid-dropdown", "is_open"),
    [Input("toggle-hybrid-dropdown", "n_clicks")],
    [State("collapse-hybrid-dropdown", "is_open")],
)
def toggle_hybrid_dropdown(n, is_open):
    if n:
        return not is_open
    return is_open

# Callback to handle irrigation data upload and update irrigation cost graph
@app.callback(
    [Output('tab2-irrigation-cost-graph', 'figure'),
     Output('tab2-irrigation-data-upload-status', 'children')],
    [Input('tab2-upload-irrigation-data', 'contents'),
     Input('tab2-price-input-irrigation', 'value'),
     Input('tab2-irrigation-date-picker', 'start_date'),
     Input('tab2-irrigation-date-picker', 'end_date')],
    [State('tab2-upload-irrigation-data', 'filename')]
)
def update_irrigation_graph(irrigation_contents, price_per_irrigation, start_date, end_date, irrigation_filename):
    if irrigation_contents is not None:
        df = parse_contents(irrigation_contents, irrigation_filename)
        if df is not None:
            if 'FarmID' not in df.columns:
                upload_status = html.Span("Error: 'FarmID' column not found in irrigation data.", style={'color': 'red'})
                return go.Figure(), upload_status
            # Melt the dataframe if dates are columns (excluding 'FarmID' and 'Total')
            date_columns = [col for col in df.columns if col not in ['FarmID', 'Total']]
            if date_columns:
                df_melted = df.melt(id_vars=['FarmID'], value_vars=date_columns, var_name='Date', value_name='Irrigation')
                df_melted['Date'] = pd.to_datetime(df_melted['Date'], errors='coerce')
                df_melted = df_melted.dropna(subset=['Date'])
                # Filter by date range
                df_filtered = df_melted[(df_melted['Date'] >= pd.to_datetime(start_date)) & (df_melted['Date'] <= pd.to_datetime(end_date))]
            else:
                upload_status = html.Span("Error: No date columns found in irrigation data.", style={'color': 'red'})
                return go.Figure(), upload_status

            # Ensure 'Irrigation' is numeric
            df_filtered['Irrigation'] = pd.to_numeric(df_filtered['Irrigation'], errors='coerce').fillna(0)

            # Calculate cost
            df_filtered['Irrigation_Cost'] = df_filtered['Irrigation'] * price_per_irrigation

            # Plot
            fig = px.bar(df_filtered, x='Date', y='Irrigation_Cost', color='FarmID',
                         title='Irrigation Cost by Date and Farm',
                         labels={'Irrigation_Cost': 'Irrigation Cost (USD)', 'Date': 'Date'},
                         template='plotly_dark')

            fig.update_layout(
                xaxis_title='Date',
                yaxis_title='Irrigation Cost (USD)',
                barmode='group',
                showlegend=True
            )

            upload_status = html.Span("Irrigation data uploaded successfully!", style={'color': 'green'})
            return fig, upload_status
        else:
            upload_status = html.Span("Error: Could not parse irrigation data file.", style={'color': 'red'})
            return go.Figure(), upload_status
    return go.Figure(), ""

# Callback to handle fertilizer data upload and update fertilizer cost graph
@app.callback(
    [Output('tab2-fertilizer-cost-graph', 'figure'),
     Output('tab2-fertilizer-data-upload-status', 'children')],
    [Input('tab2-upload-fertilizer-data', 'contents'),
     Input('tab2-price-input-fertilizer', 'value'),
     Input('tab2-irrigation-date-picker', 'start_date'),
     Input('tab2-irrigation-date-picker', 'end_date')],
    [State('tab2-upload-fertilizer-data', 'filename')]
)
def update_fertilizer_graph(fertilizer_contents, price_per_fertilizer, start_date, end_date, fertilizer_filename):
    if fertilizer_contents is not None:
        df = parse_contents(fertilizer_contents, fertilizer_filename)
        if df is not None:
            if 'FarmID' not in df.columns:
                upload_status = html.Span("Error: 'FarmID' column not found in fertilizer data.", style={'color': 'red'})
                return go.Figure(), upload_status
            # Melt the dataframe if dates are columns (excluding 'FarmID' and 'Total')
            date_columns = [col for col in df.columns if col not in ['FarmID', 'Total']]
            if date_columns:
                df_melted = df.melt(id_vars=['FarmID'], value_vars=date_columns, var_name='Date', value_name='Fertilizer')
                df_melted['Date'] = pd.to_datetime(df_melted['Date'], errors='coerce')
                df_melted = df_melted.dropna(subset=['Date'])
                # Filter by date range
                df_filtered = df_melted[(df_melted['Date'] >= pd.to_datetime(start_date)) & (df_melted['Date'] <= pd.to_datetime(end_date))]
            else:
                upload_status = html.Span("Error: No date columns found in fertilizer data.", style={'color': 'red'})
                return go.Figure(), upload_status

            # Ensure 'Fertilizer' is numeric
            df_filtered['Fertilizer'] = pd.to_numeric(df_filtered['Fertilizer'], errors='coerce').fillna(0)

            # Calculate cost
            df_filtered['Fertilizer_Cost'] = df_filtered['Fertilizer'] * price_per_fertilizer

            # Plot
            fig = px.bar(df_filtered, x='Date', y='Fertilizer_Cost', color='FarmID',
                         title='Fertilizer Cost by Date and Farm',
                         labels={'Fertilizer_Cost': 'Fertilizer Cost (USD)', 'Date': 'Date'},
                         template='plotly_dark')

            fig.update_layout(
                xaxis_title='Date',
                yaxis_title='Fertilizer Cost (USD)',
                barmode='group',
                showlegend=True
            )

            upload_status = html.Span("Fertilizer data uploaded successfully!", style={'color': 'green'})
            return fig, upload_status
        else:
            upload_status = html.Span("Error: Could not parse fertilizer data file.", style={'color': 'red'})
            return go.Figure(), upload_status
    return go.Figure(), ""

# Callback to handle total cost graph
@app.callback(
    Output('tab2-total-cost-graph', 'figure'),
    [Input('tab2-irrigation-cost-graph', 'figure'),
     Input('tab2-fertilizer-cost-graph', 'figure')]
)
def update_total_cost(irrigation_figure, fertilizer_figure):
    try:
        traces = []
        # Combine traces from both figures
        for trace in irrigation_figure.get('data', []):
            traces.append(trace)
        for trace in fertilizer_figure.get('data', []):
            traces.append(trace)

        figure = {
            'data': traces,
            'layout': go.Layout(
                title='Total Cost (Irrigation + Fertilizer) per Farm by Date',
                xaxis={'title': 'Date'},
                yaxis={'title': 'Total Cost (USD)'},
                barmode='stack',
                template='plotly_dark'
            )
        }
        logger.debug("Total cost graph updated successfully.")
        return figure
    except Exception as e:
        logger.error(f"Error updating total cost graph: {e}")
        return go.Figure()

# Callback to handle total cost per hybrid graph
@app.callback(
    Output('tab2-total-cost-per-hybrid-graph', 'figure'),
    [
        Input('tab2-upload-irrigation-data', 'contents'),
        Input('tab2-upload-irrigation-data', 'filename'),
        Input('tab2-upload-fertilizer-data', 'contents'),
        Input('tab2-upload-fertilizer-data', 'filename'),
        Input('tab2-price-input-irrigation', 'value'),
        Input('tab2-price-input-fertilizer', 'value'),
        Input('tab2-hybrid-dropdown', 'value'),
        Input('tab2-upload-planting-data', 'contents'),
        Input('tab2-upload-planting-data', 'filename')
    ]
)
def update_total_cost_per_hybrid(irrigation_contents, irrigation_filename,
                                 fertilizer_contents, fertilizer_filename,
                                 price_irrigation, price_fertilizer,
                                 selected_hybrids,
                                 planting_contents, planting_filename):
    # Initialize empty DataFrame
    total_cost_df = pd.DataFrame()

    # Process planting data
    if planting_contents is not None:
        planting_df = parse_contents(planting_contents, planting_filename)
        if planting_df is not None:
            # Ensure required columns are present
            required_columns = ['FarmID', 'PlantingDate', 'CompanyHybrid', 'Seeding Rate(plants/ac)']
            missing_columns = [col for col in required_columns if col not in planting_df.columns]
            if missing_columns:
                logger.error(f"Planting data missing columns: {missing_columns}")
                return go.Figure()
            # Filter by selected hybrids if any
            if selected_hybrids:
                planting_df = planting_df[planting_df['CompanyHybrid'].isin(selected_hybrids)]
        else:
            logger.error("Could not parse planting data.")
            return go.Figure()
    else:
        logger.error("Planting data not uploaded.")
        return go.Figure()

    # Process irrigation data
    if irrigation_contents is not None:
        irrigation_df = parse_contents(irrigation_contents, irrigation_filename)
        if irrigation_df is not None:
            if 'FarmID' not in irrigation_df.columns or 'Total' not in irrigation_df.columns:
                logger.error("Irrigation data missing 'FarmID' or 'Total' columns.")
                return go.Figure()
            # Use the 'Total' column for total irrigation per FarmID
            irrigation_summary = irrigation_df[['FarmID', 'Total']].copy()
            irrigation_summary.rename(columns={'Total': 'Irrigation_Total'}, inplace=True)
            # Calculate cost
            irrigation_summary['Irrigation_Cost'] = irrigation_summary['Irrigation_Total'] * price_irrigation
            total_cost_df = irrigation_summary
        else:
            logger.error("Could not parse irrigation data.")
            return go.Figure()

    # Process fertilizer data
    if fertilizer_contents is not None:
        fertilizer_df = parse_contents(fertilizer_contents, fertilizer_filename)
        if fertilizer_df is not None:
            if 'FarmID' not in fertilizer_df.columns or 'Total' not in fertilizer_df.columns:
                logger.error("Fertilizer data missing 'FarmID' or 'Total' columns.")
                return go.Figure()
            # Use the 'Total' column for total fertilizer per FarmID
            fertilizer_summary = fertilizer_df[['FarmID', 'Total']].copy()
            fertilizer_summary.rename(columns={'Total': 'Fertilizer_Total'}, inplace=True)
            # Calculate cost
            fertilizer_summary['Fertilizer_Cost'] = fertilizer_summary['Fertilizer_Total'] * price_fertilizer
            # Merge with total_cost_df
            if not total_cost_df.empty:
                total_cost_df = total_cost_df.merge(fertilizer_summary, on='FarmID', how='left').fillna(0)
            else:
                total_cost_df = fertilizer_summary
        else:
            logger.error("Could not parse fertilizer data.")
            return go.Figure()

    # Merge with planting data to get CompanyHybrid
    total_cost_df = total_cost_df.merge(planting_df[['FarmID', 'CompanyHybrid']], on='FarmID', how='left')

    # Calculate Total Cost
    total_cost_df['Total_Cost'] = total_cost_df['Irrigation_Cost'] + total_cost_df['Fertilizer_Cost']

    # Group by CompanyHybrid
    total_cost_per_hybrid = total_cost_df.groupby('CompanyHybrid')['Total_Cost'].sum().reset_index()

    # Plotting
    if not total_cost_per_hybrid.empty:
        fig = px.bar(
            total_cost_per_hybrid,
            x='CompanyHybrid',
            y='Total_Cost',
            color='CompanyHybrid',
            title='Total Cost per Hybrid',
            template='plotly_dark',
            labels={'CompanyHybrid': 'Hybrid', 'Total_Cost': 'Total Cost (USD)'}
        )
        fig.update_layout(
            showlegend=False,
            xaxis_title='Hybrid',
            yaxis_title='Total Cost (USD)',
            legend_title='Hybrid'
        )
        return fig
    else:
        # Return empty figure with message
        fig = go.Figure()
        fig.update_layout(
            title="Total Cost per Hybrid",
            xaxis_title="Hybrid",
            yaxis_title="Total Cost (USD)",
            template='plotly_dark',
            annotations=[
                dict(
                    text="No data available to display.",
                    xref="paper", yref="paper",
                    showarrow=False,
                    font=dict(size=20, color='white')
                )
            ]
        )
        return fig
# ----------------------------- RUN APP ----------------------------- #

# Function to open the browser after server starts
def open_browser():
    """
    Function to open the default web browser to the Dash app.
    """
    sleep(2)  # Wait for the Dash server to start
    webbrowser.open_new_tab("http://127.0.0.1:8050/")  # Default Dash port

# Start the Dash app and open the browser
if __name__ == '__main__':
    threading.Thread(target=open_browser).start()
    app.run_server(debug=True, port=8050)
