# Fetches and displays a basic candlestick app.

import dash
import plotly.graph_objects as go
import plotly.express as px
import dash_core_components as dcc
import dash_html_components as html
from dash_table import DataTable, FormatTemplate
from utils import *
from datetime import date, timedelta
from math import ceil
from backtest import *
from bloomberg_functions import req_historical_data
import numpy as np
from sklearn import linear_model
from statistics import mean

# Create a Dash app
app = dash.Dash(__name__)

# Create the page layout
app.layout = html.Div([
    html.H1(
        'Trading Strategy Example Template',
        style={'display': 'block', 'text-align': 'center'}
    ),
    html.Div([
        html.H2('Strategy'),
        html.P('This app explores a simple strategy that works as follows:'),
        html.Ol([
            html.Li([
                "While the market is not open, retrieve the past N days' " + \
                "worth of data for:",
                html.Ul([
                    html.Li("IVV: daily open, high, low, & close prices"),
                    html.Li(
                        "US Treasury CMT Rates for 1 mo, 2 mo, 3 mo, 6 mo, " + \
                        "1 yr and 2 yr maturities."
                    )
                ])
            ]),
            html.Li([
                'Fit a linear trend line through the yield curve defined ' + \
                'by the CMT rates and record in a dataframe:',
                html.Ul([
                    html.Li('the y-intercept ("a")'),
                    html.Li('the slope ("b")'),
                    html.Li('the coefficient of determination ("R^2")')
                ]),
                '...for the fitted line.'
            ]),
            html.Li(
                'Repeat 2. for past CMT data to create a FEATURES ' + \
                'dataframe containing historical values of a, b, and R^2 '
            ),
            html.Li(
                'Add volatility of day-over-day log returns of IVV ' + \
                'closing prices -- observed over the past N days -- to ' + \
                'each historical data row in the FEATURES dataframe.'
            ),
            html.Li(
                'Add RESPONSE data to the historical FEATURES dataframe.' + \
                'The RESPONSE data includes information that communicates ' + \
                'whether when, and how a limit order to SELL IVV at a ' + \
                'price equal to (IVV Open Price of Next Trading Day) * ' + \
                '(1 + alpha) would have filled over the next n trading days.'
            ),
            html.Li(
                'Using the features a, b, R^2, and IVV vol alongside the ' + \
                'RESPONSE data for the past N observed trading days, ' + \
                'train a logistic regression. Use it to predict whether a ' + \
                'limit order to SELL IVV at a price equal to (IVV Open ' + \
                'Price of Next Trading Day) * (1 + alpha) would have ' + \
                'filled over the next n trading days.'
            ),
            html.Li(
                'If the regression in 6. predicts TRUE, submit two trades:'),
            html.Ul([
                html.Li(
                    'A market order to BUY lot_size shares of IVV, which ' + \
                    'fills at open price the next trading day.'
                ),
                html.Li(
                    'A limit order to SELL lot_size shares of IVV at ' + \
                    '(next day\'s opening price * (1+alpha)'
                )
            ]),
            html.Li(
                'If the limit order does not fill after n days, issue a ' + \
                'market order to sell lot_size shares of IVV at close of ' + \
                'the nth day.'
            )
        ])
    ],
        style={'display': 'inline-block', 'width': '50%'}
    ),
    html.Div([
        html.H2('Data Note & Disclaimer'),
        html.P(
            'This Dash app makes use of Bloomberg\'s Python API to append ' + \
            'the latest historical data to what\'s already provided in the ' + \
            '.csv files in the directory \'bbg_data\'. These initial data ' + \
            'files were compiled using publicly available information on ' + \
            'the Internet and do not contain historical stock market data ' + \
            'from Bloomberg. This app does NOT need a Bloomberg ' + \
            'subscription to work -- only to update data. Always know and ' + \
            'obey your data stewardship obligations!'
        ),
        html.H2('Parameters'),
        html.Ol([
            html.Li(
                "n: number of days a limit order to exit a position is " + \
                "kept open"
            ),
            html.Li(
                "N: number of observed historical trading days to use in " + \
                "training the logistic regression model."
            ),
            html.Li(
                'alpha: a percentage in numeric form ' + \
                '(e.g., "0.02" == "2%") that defines the profit sought by ' + \
                'entering a trade; for example, if IVV is bought at ' + \
                'price X, then a limit order to sell the shares will be put' + \
                ' in place at a price = X*(1+alpha)'
            ),
            html.Li(
                'lot_size: number of shares traded in each round-trip ' + \
                'trade. Kept constant for simplicity.'
            ),
            html.Li(
                'date_range: Date range over which to perform the backtest.'
            )
        ]),
        html.Div(
            [
                html.Div(
                    [
                        html.Button(
                            "RUN BACKTEST", id='run-backtest', n_clicks=0
                        ),
                        html.Table(
                            [html.Tr([
                                html.Th('Alpha'), html.Th('Beta'),
                                html.Th('Geometric Mean Return'),
                                html.Th('Average Trades per Year'),
                                html.Th('Volatility'), html.Th('Sharpe')
                            ])] + [html.Tr([
                                html.Td(html.Div(id='strategy-alpha')),
                                html.Td(html.Div(id='strategy-beta')),
                                html.Td(html.Div(id='strategy-gmrr')),
                                html.Td(html.Div(id='strategy-trades-per-yr')),
                                html.Td(html.Div(id='strategy-vol')),
                                html.Td(html.Div(id='strategy-sharpe'))
                            ])],
                            className='main-summary-table'
                        ),
                        html.Table(
                            # Header
                            [html.Tr([
                                html.Th('Date Range'),
                                html.Th('Bloomberg Identifier'),
                                html.Th('n'), html.Th('N'), html.Th('alpha'),
                                html.Th('Lot Size'),
                                html.Th('Starting Cash')
                            ])] +
                            # Body
                            [html.Tr([
                                html.Td(
                                    dcc.DatePickerRange(
                                        id='hist-data-range',
                                        min_date_allowed=date(2015, 1, 1),
                                        max_date_allowed=date.today(),
                                        initial_visible_month=date.today(),
                                        start_date=date(2019, 3, 16),
                                        end_date=date(2021, 4, 12)
                                    )
                                ),
                                html.Td(dcc.Input(
                                    id='bbg-identifier-1', type="text",
                                    value="IVV US Equity",
                                    style={'text-align': 'center'}
                                )),
                                html.Td(
                                    dcc.Input(
                                        id='lil-n', type="number", value=5,
                                        style={'text-align': 'center',
                                               'width': '30px'}
                                    )
                                ),
                                html.Td(
                                    dcc.Input(
                                        id='big-N', type="number", value=10,
                                        style={'text-align': 'center',
                                               'width': '50px'}
                                    )
                                ),
                                html.Td(
                                    dcc.Input(
                                        id="alpha", type="number", value=0.02,
                                        style={'text-align': 'center',
                                               'width': '50px'}
                                    )
                                ),
                                html.Td(
                                    dcc.Input(
                                        id="lot-size", type="number", value=100,
                                        style={'text-align': 'center',
                                               'width': '50px'}
                                    )
                                ),
                                html.Td(
                                    dcc.Input(
                                        id="starting-cash", type="number",
                                        value=50000,
                                        style={'text-align': 'center',
                                               'width': '100px'}
                                    )
                                )
                            ])]
                        )
                    ],
                    style={'display': 'inline-block', 'width': '50%'}
                )
            ],
            style={'display': 'block'}
        )
    ],
        style={
            'display': 'inline-block', 'width': '50%', 'vertical-align': 'top'
        }
    ),
    ##### Intermediate Variables (hidden in divs as JSON) ######################
    ############################################################################
    # Hidden div inside the app that stores IVV historical data
    html.Div(id='ivv-hist', style={'display': 'none'}),
    # Hidden div inside the app that stores bonds historical data
    html.Div(id='bonds-hist', style={'display': 'none'}),
    ############################################################################
    ############################################################################
    html.Div(
        [dcc.Graph(id='alpha-beta')],
        style={'display': 'inline-block', 'width': '50%'}
    ),
    # Display the current selected date range
    html.Div(id='date-range-output'),
    html.Div([
        html.H2(
            'Trade Ledger',
            style={
                'display': 'inline-block', 'text-align': 'center',
                'width': '100%'
            }
        ),
        DataTable(
            id='trade-ledger',
            fixed_rows={'headers': True},
            style_cell={'textAlign': 'center'},
            style_table={'height': '300px', 'overflowY': 'auto'}
        )
    ]),
    html.Div([
        html.Div([
            html.H2(
                'Calendar Ledger',
                style={
                    'display': 'inline-block', 'width': '45%',
                    'text-align': 'center'
                }
            ),
            html.H2(
                'Trade Blotter',
                style={
                    'display': 'inline-block', 'width': '55%',
                    'text-align': 'center'
                }
            )
        ]),
        html.Div(
            DataTable(
                id='calendar-ledger',
                fixed_rows={'headers': True},
                style_cell={'textAlign': 'center'},
                style_table={'height': '300px', 'overflowY': 'auto'}
            ),
            style={'display': 'inline-block', 'width': '45%'}
        ),
        html.Div(
            DataTable(
                id='blotter',
                fixed_rows={'headers': True},
                style_cell={'textAlign': 'center'},
                style_table={'height': '300px', 'overflowY': 'auto'}
            ),
            style={'display': 'inline-block', 'width': '55%'}
        )
    ]),
    html.Div([
        html.H2(
            'Features and Responses',
            style={
                'display': 'inline-block', 'text-align': 'center',
                'width': '100%'
            }
        ),
        DataTable(
            id='features-and-responses',
            fixed_rows={'headers': True},
            style_cell={'textAlign': 'center'},
            style_table={'height': '300px', 'overflowY': 'auto'}
        )
    ]),
    html.Div([
        html.Div(
            dcc.Graph(id='bonds-3d-graph', style={'display': 'none'}),
            style={'display': 'inline-block', 'width': '50%'}
        ),
        html.Div(
            dcc.Graph(id='candlestick', style={'display': 'none'}),
            style={'display': 'inline-block', 'width': '50%'}
        )
    ]),
    html.Div(id='proposed-trade'),
    ############################################################################
    ############################################################################
])


@app.callback(
    #### Update Historical Bloomberg Data
    [dash.dependencies.Output('ivv-hist', 'children'),
     dash.dependencies.Output('date-range-output', 'children'),
     dash.dependencies.Output('candlestick', 'figure'),
     dash.dependencies.Output('candlestick', 'style')],
    dash.dependencies.Input("run-backtest", 'n_clicks'),
    [dash.dependencies.State("bbg-identifier-1", "value"),
     dash.dependencies.State("big-N", "value"),
     dash.dependencies.State("lil-n", "value"),
     dash.dependencies.State('hist-data-range', 'start_date'),
     dash.dependencies.State('hist-data-range', 'end_date')],
    prevent_initial_call=True
)
def update_bbg_data(nclicks, bbg_id_1, N, n, start_date, end_date):
    # Need to query enough days to run the backtest on every date in the
    # range start_date to end_date
    start_date = pd.to_datetime(start_date).date() - timedelta(
        days=ceil((N + n) * (365 / 252))
    )
    start_date = start_date.strftime("%Y-%m-%d")

    historical_data = req_historical_data(bbg_id_1, start_date, end_date)

    date_output_msg = 'Backtesting from '

    if start_date is not None:
        start_date_object = date.fromisoformat(start_date)
        start_date_string = start_date_object.strftime('%B %d, %Y')
        date_output_msg = date_output_msg + 'Start Date: ' + \
                          start_date_string + ' to '

    if end_date is not None:
        end_date_object = date.fromisoformat(end_date)
        end_date_string = end_date_object.strftime('%B %d, %Y')
        date_output_msg = date_output_msg + 'End Date: ' + end_date_string
    if len(date_output_msg) == len('You have selected: '):
        date_output_msg = 'Select a date to see it displayed here'

    fig = go.Figure(
        data=[
            go.Candlestick(
                x=historical_data['Date'],
                open=historical_data['Open'],
                high=historical_data['High'],
                low=historical_data['Low'],
                close=historical_data['Close']
            )
        ]
    )

    return historical_data.to_json(), date_output_msg, fig, {'display': 'block'}


@app.callback(
    [dash.dependencies.Output('bonds-hist', 'children'),
     dash.dependencies.Output('bonds-3d-graph', 'figure'),
     dash.dependencies.Output('bonds-3d-graph', 'style')],
    dash.dependencies.Input("run-backtest", 'n_clicks'),
    [dash.dependencies.State('hist-data-range', 'start_date'),
     dash.dependencies.State('hist-data-range', 'end_date'),
     dash.dependencies.State('big-N', 'value'),
     dash.dependencies.State('lil-n', 'value')
     ],
    prevent_initial_call=True
)
def update_bonds_hist(n_clicks, startDate, endDate, N, n):
    # Need to query enough days to run the backtest on every date in the
    # range start_date to end_date
    startDate = pd.to_datetime(startDate).date() - timedelta(
        days=ceil((N + n) * (365 / 252))
    )
    startDate = startDate.strftime("%Y-%m-%d")

    data_years = list(
        range(pd.to_datetime(startDate).date().year,
              pd.to_datetime(endDate).date().year + 1, 1)
    )

    bonds_data = fetch_usdt_rates(data_years[0])

    if len(data_years) > 1:
        for year in data_years[1:]:
            bonds_data = pd.concat([bonds_data, fetch_usdt_rates(year)],
                                   axis=0, ignore_index=True)

    # How to filter a dataframe for rows that you want
    bonds_data = bonds_data[bonds_data.Date >= pd.to_datetime(startDate)]
    bonds_data = bonds_data[bonds_data.Date <= pd.to_datetime(endDate)]

    fig = go.Figure(
        data=[
            go.Surface(
                z=bonds_data,
                y=bonds_data.Date,
                x=[
                    to_years(cmt_colname) for cmt_colname in list(
                        filter(lambda x: ' ' in x, bonds_data.columns.values)
                    )
                ]
            )
        ]
    )

    fig.update_layout(
        scene=dict(
            xaxis_title='Maturity (years)',
            yaxis_title='Date',
            zaxis_title='APR (%)',
            zaxis=dict(ticksuffix='%')
        )
    )

    bonds_data.reset_index(drop=True, inplace=True)

    return bonds_data.to_json(), fig, {'display': 'block'}


@app.callback(
    [
        dash.dependencies.Output('features-and-responses', 'data'),
        dash.dependencies.Output('features-and-responses', 'columns'),
        dash.dependencies.Output('blotter', 'data'),
        dash.dependencies.Output('blotter', 'columns'),
        dash.dependencies.Output('calendar-ledger', 'data'),
        dash.dependencies.Output('calendar-ledger', 'columns'),
        dash.dependencies.Output('trade-ledger', 'data'),
        dash.dependencies.Output('trade-ledger', 'columns')
    ],
    [dash.dependencies.Input('ivv-hist', 'children'),
     dash.dependencies.Input('bonds-hist', 'children'),
     dash.dependencies.Input('lil-n', 'value'),
     dash.dependencies.Input('big-N', 'value'),
     dash.dependencies.Input('alpha', 'value'),
     dash.dependencies.Input('lot-size', 'value'),
     dash.dependencies.Input('starting-cash', 'value'),
     dash.dependencies.State('hist-data-range', 'start_date'),
     dash.dependencies.State('hist-data-range', 'end_date')],
    prevent_initial_call=True
)
def calculate_backtest(ivv_hist, bonds_hist, n, N, alpha, lot_size,
                       starting_cash, start_date, end_date):
    features_and_responses, blotter, calendar_ledger, trade_ledger = backtest(
        ivv_hist, bonds_hist, n, N, alpha, lot_size, start_date, end_date,
        starting_cash
    )

    features_and_responses_columns = [
        {"name": i, "id": i} for i in features_and_responses.columns
    ]
    features_and_responses = features_and_responses.to_dict('records')

    blotter = blotter.to_dict('records')
    blotter_columns = [
        dict(id='ID', name='ID'),
        dict(id='ls', name='long/short'),
        dict(id='submitted', name='Created'),
        dict(id='action', name='Action'),
        dict(id='size', name='Size'),
        dict(id='symbol', name='Symb'),
        dict(
            id='price', name='Order Price', type='numeric',
            format=FormatTemplate.money(2)
        ),
        dict(id='type', name='Type'),
        dict(id='status', name='Status'),
        dict(id='fill_price', name='Fill Price', type='numeric',
             format=FormatTemplate.money(2)
             ),
        dict(id='filled_or_cancelled', name='Filled/Cancelled')
    ]

    calendar_ledger = calendar_ledger.to_dict('records')
    calendar_ledger_columns = [
        dict(id='Date', name='Date'),
        dict(id='position', name='position'),
        dict(id='ivv_close', name='IVV Close', type='numeric',
             format=FormatTemplate.money(2)),
        dict(id='cash', name='Cash', type='numeric',
             format=FormatTemplate.money(2)),
        dict(id='stock_value', name='Stock Value', type='numeric',
             format=FormatTemplate.money(2)),
        dict(id='total_value', name='Total Value', type='numeric',
             format=FormatTemplate.money(2))
    ]

    trade_ledger = trade_ledger.to_dict('records')
    trade_ledger_columns = [
        dict(id='trade_id', name="ID"),
        dict(id='open_dt', name='Trade Opened'),
        dict(id='close_dt', name='Trade Closed'),
        dict(id='trading_days_open', name='Trading Days Open'),
        dict(id='buy_price', name='Entry Price', type='numeric',
             format=FormatTemplate.money(2)),
        dict(id='sell_price', name='Exit Price', type='numeric',
             format=FormatTemplate.money(2)),
        dict(id='benchmark_buy_price', name='Benchmark Buy Price',
             type='numeric', format=FormatTemplate.money(2)),
        dict(id='benchmark_sell_price', name='Benchmark sell Price',
             type='numeric', format=FormatTemplate.money(2)),
        dict(id='trade_rtn', name='Return on Trade', type='numeric',
             format=FormatTemplate.percentage(3)),
        dict(id='benchmark_rtn', name='Benchmark Return', type='numeric',
             format=FormatTemplate.percentage(3)),
        dict(id='trade_rtn_per_trading_day', name='Trade Rtn / trd day',
             type='numeric', format=FormatTemplate.percentage(3)),
        dict(id='benchmark_rtn_per_trading_day', name='Benchmark Rtn / trd day',
             type='numeric', format=FormatTemplate.percentage(3))
    ]

    return features_and_responses, features_and_responses_columns, blotter, \
           blotter_columns, calendar_ledger, calendar_ledger_columns, \
           trade_ledger, trade_ledger_columns


@app.callback(
    [
        dash.dependencies.Output('alpha-beta', 'figure'),
        dash.dependencies.Output('strategy-alpha', 'children'),
        dash.dependencies.Output('strategy-beta', 'children'),
        dash.dependencies.Output('strategy-gmrr', 'children'),
        dash.dependencies.Output('strategy-trades-per-yr', 'children'),
        dash.dependencies.Output('strategy-vol', 'children'),
        dash.dependencies.Output('strategy-sharpe', 'children')
    ],
    dash.dependencies.Input('trade-ledger', 'data'),
    prevent_initial_call=True
)
def update_performance_metrics(trade_ledger):
    trade_ledger = pd.DataFrame(trade_ledger)
    trade_ledger = trade_ledger[1:]

    X = trade_ledger['benchmark_rtn_per_trading_day'].values.reshape(-1, 1)

    linreg_model = linear_model.LinearRegression()
    linreg_model.fit(X, trade_ledger['trade_rtn_per_trading_day'])

    x_range = np.linspace(X.min(), X.max(), 100)
    y_range = linreg_model.predict(x_range.reshape(-1, 1))

    fig = px.scatter(
        trade_ledger,
        title="Performance against Benchmark",
        x='benchmark_rtn_per_trading_day',
        y='trade_rtn_per_trading_day'
    )

    fig.add_traces(go.Scatter(x=x_range, y=y_range, name='OLS Fit'))

    alpha = str(round(linreg_model.intercept_ * 100, 3)) + "% / trade"
    beta = round(linreg_model.coef_[0], 3)

    gmrr = (trade_ledger['trade_rtn_per_trading_day'] + 1).product() ** (
            1 / len(
        trade_ledger)) - 1

    avg_trades_per_yr = round(
        trade_ledger['open_dt'].groupby(
            pd.DatetimeIndex(trade_ledger['open_dt']).year
        ).agg('count').mean(),
        0
    )

    vol = stdev(trade_ledger['trade_rtn_per_trading_day'])

    sharpe = round(gmrr / vol, 3)

    gmrr_str = str(round(gmrr, 3)) + "% / trade"

    vol_str = str(round(vol, 3)) + "% / trade"

    return fig, alpha, beta, gmrr_str, avg_trades_per_yr, vol_str, sharpe


# Run it!
if __name__ == '__main__':
    app.run_server(debug=True)
