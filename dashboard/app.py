"""
File:           app.py
Author:         Dibyaranjan Sathua
Created on:     07/11/22, 9:56 pm
"""
import datetime
import time

from dash import Dash, html, dcc, Input, Output, State
import dash_daq as daq
import dash_bootstrap_components as dbc
import dash_auth

from dashboard.db import SessionLocal
from dashboard.db.db_api import DBApi
from src.utils.redis_backend import RedisBackend


db = SessionLocal()
VALID_USERNAME_PASSWORD_PAIRS = {
    user.username: user.password for user in DBApi.get_users(db)
}

redis_backend = RedisBackend()
redis_backend.connect()

app = Dash(
    __name__, meta_tags=[{"name": "viewport", "content": "width=device-width"}],
)
app.title = "AlgoTrading Dashboard"
server = app.server
auth = dash_auth.BasicAuth(
    app,
    VALID_USERNAME_PASSWORD_PAIRS
)


def single_day_settings(day: str):
    return html.Div(
        className=f"{day.lower()}-settings",
        children=[
            html.Div(
                className="four columns",
                children=[
                    html.H4(f"{day.capitalize()}")
                ]
            ),
            html.Div(
                className="four columns",
                children=[
                    daq.BooleanSwitch(
                        id=f"{day.lower()}-power-btn", on=False, color="#00418e"
                    ),
                ]
            ),
            html.Div(
                className="four columns",
                children=[
                    dcc.Input(
                        id=f"{day.lower()}-time-input", placeholder="HH:MM"
                    )
                ]
            ),
        ]
    )


def day_settings():
    return html.Div(
        className="day-settings",
        children=[
            html.Div(
                children=[
                    html.H3("Day Settings"),
                    html.Div(className="row", children=single_day_settings("monday")),
                    html.Div(className="row", children=single_day_settings("tuesday")),
                    html.Div(className="row", children=single_day_settings("wednesday")),
                    html.Div(className="row", children=single_day_settings("thursday")),
                    html.Div(className="row", children=single_day_settings("friday")),
                    html.Div(
                        className="row",
                        children=html.Button(
                            "Save",
                            id="day-settings-save-btn",
                            n_clicks=0,
                            style={"float": "right"}
                        )
                    )
                ]
            ),

        ]
    )


def manual_entry_exit_buttons():
    return html.Div(
        className="manual-exe-btn",
        children=[
            html.Div(
                className="six columns",
                children=[
                    html.Button("Entry", id="manual-entry-btn", n_clicks=0)
                ]
            ),
            html.Div(
                className="six columns",
                children=[
                    html.Button("Exit", id="manual-exit-btn", n_clicks=0)
                ]
            ),
        ]
    )


def manual_execution():
    return html.Div(
        className="manual-execution",
        children=[
            html.Div(
                children=[
                    html.H3("Manual Execution"),
                    html.Div(className="row", children=manual_entry_exit_buttons())
                ]
            )
        ]
    )


# Layout of Dash App
app.layout = html.Div(
    children=[
        # Header
        html.Div(
            id="header",
            className="row banner",
            children=[
                # Logo and Title
                html.Div(
                    className="banner-logo-and-title",
                    children=[
                        html.H2(
                            "AlgoTrading: Shorting Straddle"
                        ),
                    ],
                ),
                # Toggle
                html.Div(
                    className="row power-div",
                    children=daq.BooleanSwitch(
                        id="algo-power-btn", on=False, color="#00418e"
                    ),
                ),
                # Dummy div for Config Save output
                html.Div(children="", id="display-message", style={"display": "none"}),
                # Dummy div for power button callback
                html.Div(children="", id="power-btn-callback", style={"display": "none"}),
                # Dummy div for manual exit callback
                html.Div(children="", id="manual-exit-callback", style={"display": "none"})
            ],
        ),
        html.Div(
            className="row",
            children=[
                # Left panel - settings
                html.Div(
                    className="five columns div-user-controls",
                    children=[
                        day_settings(),
                        manual_execution(),
                    ],
                ),
                # Column for app graphs and plots
                html.Div(
                    className="seven columns div-for-charts bg-grey",
                    children=[
                        html.Div(
                            className="text-padding",
                            children=[
                                "Show the results"
                            ],
                        ),
                    ],
                ),
            ],
        )
    ]
)


# Callbacks
@app.callback(
    [
        Output("monday-power-btn", "on"),
        Output("monday-time-input", "value"),
        Output("monday-time-input", "disabled"),
        Output("tuesday-power-btn", "on"),
        Output("tuesday-time-input", "value"),
        Output("tuesday-time-input", "disabled"),
        Output("wednesday-power-btn", "on"),
        Output("wednesday-time-input", "value"),
        Output("wednesday-time-input", "disabled"),
        Output("thursday-power-btn", "on"),
        Output("thursday-time-input", "value"),
        Output("thursday-time-input", "disabled"),
        Output("friday-power-btn", "on"),
        Output("friday-time-input", "value"),
        Output("friday-time-input", "disabled"),
    ],
    [
        Input("algo-power-btn", "on")
    ]
)
def algo_power_btn_callback(on):
    DBApi.update_algo_power_status(db, on)
    run_config = DBApi.get_run_config(db)
    if on:
        output = [[config.run, config.time, False] for config in run_config]
    else:
        output = [[on, config.time, True] for config in run_config]
    return [y for x in output for y in x]  # Flattening the list


@app.callback(
    [
        Output("display-message", "children"),
    ],
    [
        Input("day-settings-save-btn", "n_clicks"),
    ],
    [
        State("monday-power-btn", "on"),
        State("monday-time-input", "value"),
        State("tuesday-power-btn", "on"),
        State("tuesday-time-input", "value"),
        State("wednesday-power-btn", "on"),
        State("wednesday-time-input", "value"),
        State("thursday-power-btn", "on"),
        State("thursday-time-input", "value"),
        State("friday-power-btn", "on"),
        State("friday-time-input", "value"),
    ]
)
def save_run_config_callback(n_clicks, *args):
    if not n_clicks:
        return [""]
    data = dict()
    for index, day in enumerate(("monday", "tuesday", "wednesday", "thursday", "friday")):
        d_time = args[2 * index + 1] or ""      # Sometimes time value is None
        try:
            d_time = datetime.datetime.strptime(d_time, "%H:%M:%S").time()
        except ValueError:
            d_time = None
        data[day] = {
            "run": args[2 * index],
            "time": d_time
        }
    DBApi.update_run_config(db, data)
    return ["Config saved successfully"]


@app.callback(
    [
        Output("algo-power-btn", "on")
    ],
    [
        Input("power-btn-callback", "children")
    ]
)
def load_initial_power_state(children):
    power_state = DBApi.get_algo_power(db)
    return [power_state.on]


@app.callback(
    [
        Output("manual-exit-callback", "children")
    ],
    [
        Input("manual-exit-btn", "n_clicks")
    ]
)
def manual_exit_callback(n_clicks):
    if not n_clicks:
        return [""]
    redis_backend.connect()
    redis_backend.set("MANUAL_EXIT", "True")
    return [""]


if __name__ == "__main__":
    app.run_server(debug=True)
