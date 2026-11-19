import numpy as np
import pandas as pd
import plotly.express as px


def coverage(table):
    """table: one row per year, share = member days with prices / member days"""
    return px.line(table.reset_index(), x='year', y='share', markers=True, range_y=[0, 1.05],
                   title='Share of S&P 500 member days with Yahoo prices')


def members_per_day(members):
    """members: one row per member day with prices"""
    counts = members.groupby('date').size().rename('members').reset_index()
    return px.line(counts, x='date', y='members', title='S&P 500 members with prices on each day')


def yearly_vs_spy(table):
    """table: one row per year, columns members and spy, each that year's return"""
    long = table.reset_index().melt(id_vars='year', var_name='who', value_name='return')
    return px.bar(long, x='year', y='return', color='who', barmode='group',
                  title='Return each year: the average member against SPY')


def spy_with_average(market):
    """market: date, spy_close, spy_200 (the average close over the last 200 days)"""
    return px.line(market, x='date', y=['spy_close', 'spy_200'], log_y=True,
                   title='SPY and its 200-day average (log scale)')


def drawdown(market):
    """market: date, drawdown = how far SPY is below its highest close so far"""
    return px.area(market, x='date', y='drawdown', title='SPY below its last peak')


def vix(market):
    return px.line(market, x='date', y='vix_close', title='VIX')


def hist(values, bins, title, x_title):
    """values: one number per row, counted into bins before drawing"""
    counts, edges = np.histogram(values, bins=bins)
    table = pd.DataFrame({x_title: (edges[:-1] + edges[1:]) / 2, 'count': counts})
    return px.bar(table, x=x_title, y='count', title=title)


def binned_mean(x, y, bins, x_title, y_title, title):
    """the average of y over the rows whose x falls in each bin"""
    table = y.groupby(pd.cut(x, bins), observed=True).agg(['mean', 'size'])
    table.index = [interval.mid for interval in table.index]
    table = table.reset_index().rename(columns={'index': x_title, 'mean': y_title, 'size': 'days'})
    return px.bar(table, x=x_title, y=y_title, hover_data=['days'], title=title)


def rolling_vol(market):
    """market: date, spy_vol = SPY's swing over the last 63 days, as a yearly figure"""
    return px.line(market, x='date', y='spy_vol', title="SPY's volatility over the last 3 months")


def return_hist(returns, width, title):
    """returns: one return per row, counted into bins of the given width
    next to the counts a bell curve (normal) with the same mean and spread would give"""
    counts, edges = np.histogram(returns, bins=np.arange(returns.min(), returns.max() + width, width))
    mid = (edges[:-1] + edges[1:]) / 2

    # normal density f(r) = exp(-z^2 / 2) / (s sqrt(2 pi)) with z = (r - mean) / s, times n and the bin width
    z = (mid - returns.mean()) / returns.std()
    bell = len(returns) * width * np.exp(-z ** 2 / 2) / (returns.std() * np.sqrt(2 * np.pi))

    # bins with no rows, and bell values under one row, are left off so the log axis stays readable
    table = pd.DataFrame({'return': mid, 'actual': np.where(counts >= 1, counts, np.nan),
                          'bell curve': np.where(bell >= 1, bell, np.nan)})
    return px.line(table, x='return', y=['actual', 'bell curve'], log_y=True, title=title)


def autocorr(table):
    """table: lag, return, size of move, each the correlation of today with that many days before"""
    return px.line(table, x='lag', y=['return', 'size of move'], markers=True,
                   title="SPY: how much today's move goes with the move some days before")


def corr_by_year(table):
    """table: one row per year, corr = average correlation between two members' daily returns"""
    return px.bar(table.reset_index(), x='year', y='corr',
                  title="Average correlation between two members' daily returns")


def spy_volume(market):
    """market: date, spy_volume, averaged per month before drawing"""
    monthly = market.set_index('date')['spy_volume'].resample('ME').mean().reset_index()
    return px.line(monthly, x='date', y='spy_volume', title="SPY's average daily volume each month")


def beat_share(table, k):
    """table: one row per year, share = member days that beat SPY over the next k days"""
    fig = px.bar(table.reset_index(), x='year', y='share', range_y=[0, 1],
                 title=f'Share of member days that beat SPY over the next {k} days')
    fig.add_hline(y=0.5, line_dash='dash')
    return fig


def membership_spans(spans):
    """spans: ticker, start, end, one row per run of days in the index"""
    return px.timeline(spans, x_start='start', x_end='end', y='ticker', title='Days in the S&P 500')


def growth(prices):
    """prices: one column per ticker, one row per day, divided by the first day's value and taken at each month's end"""
    monthly = (prices / prices.iloc[0]).resample('ME').last()
    monthly = monthly.reset_index().melt(id_vars='date', var_name='ticker', value_name='growth')
    return px.line(monthly, x='date', y='growth', color='ticker', log_y=True, title='What $1 grew to (log scale)')


def excess_by_year(table):
    """table: one row per year, one column per ticker, each that year's return minus SPY's"""
    long = table.reset_index().melt(id_vars='year', var_name='ticker', value_name='return minus spy')
    return px.bar(long, x='year', y='return minus spy', color='ticker', barmode='group',
                  title="Each year's return minus SPY's")
