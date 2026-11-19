# Notebook examples

Cells copied from real coursework notebooks. Read for the shape: why the notebook exists, the words it uses, short code cells, one plot call per cell, plain `###` lines with the numbers under each output, and a numbered summary at the end.

## A. A data notebook (ml_project/01_data.ipynb, selected cells)

markdown cell
```markdown
# Trading on Judgement: Data
```

markdown cell
```markdown
## 1. Why this notebook
### Every later notebook needs two things for each trading day since 1996: which companies were in the S&P 500 that day, and their prices.
### The members on a day are used to describe the whole market that day (regime and mood), and to pick stocks that might beat the market.
```

markdown cell
```markdown
### Words used here
### Stock: a small piece of a company that people buy and sell. Its price moves every day.
### Ticker: the short code a stock trades under. NVDA is Nvidia, AAPL is Apple. A company can change its ticker, and an old ticker can be given to a new company.
### S&P 500: an index, meaning a list of about 500 of the biggest US companies tracked together as one number. Companies are added and removed over time, so the list in 1999 is not the list today.
### Member: a company that is on the list on a given day. Membership says who was a member on each day.
### Trading day: a day the US stock market is open, about 252 a year.
### Open, high, low, close, volume: the first price of the day, the highest, the lowest, the last, and how many shares changed hands.
### Adjusted prices: when a company splits each share into smaller ones (a split) or pays cash to its owners (a dividend), the price drops but nobody loses money. Adjusting rewrites the old prices so those days don't look like crashes.
### SPY: a fund that holds all the S&P 500 companies, so its price is the market as a whole.
### VIX: how much traders expect the market to swing over the next 30 days. A high VIX means fear.
### Delisted: a company that stopped trading, because another company bought it or it went bankrupt.
```

markdown cell
```markdown
## 2. Who was in the index
### The S&P 500 member list on every date it changed, from fja05680/sp500 on GitHub (MIT licence).
```

code cell
```python
url = 'https://raw.githubusercontent.com/fja05680/sp500/master/S%26P%20500%20Historical%20Components%20%26%20Changes%20(Updated).csv'
os.makedirs('data/raw', exist_ok=True)
if not os.path.exists('data/raw/members.csv'):
    urllib.request.urlretrieve(url, 'data/raw/members.csv')

changes = pd.read_csv('data/raw/members.csv', parse_dates=['date'])
changes['tickers'] = changes['tickers'].str.split(',')
changes.head()
```

code cell
```python
sizes = changes['tickers'].str.len()
len(changes), changes['date'].min().date(), changes['date'].max().date(), sizes.min(), sizes.max()
```

markdown cell
```markdown
### 2720 change dates from 1996-01-02 to 2026-08-18. Each row holds the full list, 487 to 507 names.
### Not always 500, because an addition and its removal don't always land on the same day.
### The list's author built 1996-2019 from Andreas Clenow's list and couldn't check it before 2001.

---
```

markdown cell
```markdown
## 6. Renamed companies
### When a company changes its ticker, the list switches to the new ticker that day, but Yahoo files the company's whole history under the new one. So the member days under the old ticker had no prices, Facebook's years as FB for example.
### How we found them: before this section, the members missing the most days (section 9) included companies that still trade, like Facebook (FB) and Gap (GPS). For most of them, on the day the old ticker left the list a new ticker joined whose Yahoo prices go back years. We searched the web for each one, and the company's press release or SEC filing confirmed the change and its date.
### Most only changed their name or ticker. The second group are mergers where the member's shares carried on under a new ticker, like BB&T becoming Truist (TFC) and Harris becoming L3Harris (LHX).
### Gap (GPS) and Alliance Data (ADS) changed ticker after they left the index, so GAP and BFH were never in the list. Section 3 downloads them on their own.
```

code cell
```python
# old ticker: ticker today, each one confirmed by a web search
renamed = {'FB': 'META', 'ARNC': 'HWM', 'PKI': 'RVTY', 'BLL': 'BALL', 'LB': 'BBWI', 'ABC': 'COR', 'CTL': 'LUMN',
           'BK': 'BNY', 'MMC': 'MRSH', 'SATS': 'ECHO', 'BHGE': 'BKR', 'TMK': 'GL', 'ANTM': 'ELV', 'JEC': 'J',
           'WLTW': 'WTW', 'RE': 'EG', 'FLT': 'CPAY', 'SYMC': 'GEN', 'NLOK': 'GEN', 'DWDP': 'DD',
           'GPS': 'GAP', 'ADS': 'BFH',
           # mergers: the member's shares carried on under the new ticker
           'UTX': 'RTX', 'BBT': 'TFC', 'HRS': 'LHX', 'MYL': 'VTRS', 'PX': 'LIN', 'PEAK': 'DOC', 'EQR': 'VMRK'}

old = members[members['ticker'].isin(renamed)].groupby('ticker').agg(first=('date', 'min'), last=('date', 'max'),
                                                                      days=('date', 'size'))
old['today'] = old.index.map(renamed)
old['yahoo_from'] = old['today'].map(prices.groupby('ticker')['date'].min())
old.sort_values('last')
```

markdown cell
```markdown
### Each old ticker, the days it was a member under it, the ticker today, and the first day Yahoo has prices under that one.
### Yahoo's prices cover the old member days for all but HWM. The list writes Alcoa Inc as ARNC back to 1996, and Alcoa Inc became Arconic Inc on 2016-11-01, the day Yahoo's HWM starts. Section 7 keeps HWM from that day on.

---
```

markdown cell
```markdown
## 9. Coverage
### For each year: trading days, members on an average day, how many of them have prices, and the share.
```

code cell
```python
priced = pd.MultiIndex.from_frame(prices.loc[prices['in_index'], ['date', 'ticker']])
members['has_price'] = pd.MultiIndex.from_frame(members[['date', 'ticker']]).isin(priced)

coverage = members.groupby(members['date'].dt.year.rename('year')).agg(days=('date', 'nunique'),
                                                                       member_days=('ticker', 'size'),
                                                                       priced=('has_price', 'sum'))
coverage['members'] = (coverage['member_days'] / coverage['days']).round(1)
coverage['with_prices'] = (coverage['priced'] / coverage['days']).round(1)
coverage['share'] = (coverage['priced'] / coverage['member_days']).round(3)
coverage = coverage[['days', 'members', 'with_prices', 'share']]
coverage
```

code cell
```python
plots.coverage(coverage)
```

markdown cell
```markdown
### We see 40% of the index in 1996, just under half until 2000, half from 2001, 68% in 2010, 91% in 2020 and 98% in 2026.
### This gap is the survivorship bias that is left: the further back, the more of the index is missing.

---
```

markdown cell
```markdown
## 11. Summary
### 1. 1209 tickers were in the S&P 500 at some point from 1996 to 2026. Yahoo has prices under 751 of them, and under GAP and BFH for two members that changed ticker after leaving.
### 2. 7769 trading days from 1996-01-02 to 2026-11-13, with about 498 members on each day.
### 3. Old tickers of companies that still trade are linked to the ticker they have today (FB to META, UTX to RTX), each confirmed by a web search. IR and TT are split by date, because each meant two companies.
### 4. Cleaning: 33 tickers with under 2 years of prices are dropped. 107 membership stretches belong to a later company with the same symbol and get no prices, 6 more turned out to be the same company and keep theirs. EP and PARA are other securities and are dropped.
### 5. stock_days: 4,167,915 rows of 626 stocks, 2,732,420 of them on days the stock was a member. market: SPY and VIX on all 7769 days, nothing missing.
### 6. Coverage: 40% of the index in 1996, half from 2001, 98% in 2026. Survivorship bias is reduced, not removed, and the early years carry most of it.
```

## B. One check inside an EDA notebook (ml_project/02_eda.ipynb)

markdown cell
```markdown
### The one survivorship check we can measure: each year, the return of the average member against SPY's.
### If dead companies are missing, the members we see did better than the real index, and the gap should be widest in the early years when we see the least.
### An equal average of members differs from SPY even with nothing missing, since SPY gives big companies more weight. So the gap is only partly survivorship.
```

code cell
```python
daily_avg = pd.DataFrame({'members': members.groupby('date')['ret'].mean(), 'spy': mkt.set_index('date')['spy_ret']})
yearly = (1 + daily_avg).groupby(daily_avg.index.year).prod() - 1
yearly.index.name = 'year'
plots.yearly_vs_spy(yearly)
```

code cell
```python
yearly['gap'] = yearly['members'] - yearly['spy']
yearly.round(3).T
```

code cell
```python
yearly['gap'].groupby(yearly.index <= 2012).mean().round(3)
```

markdown cell
```markdown
### The average member beat SPY by 7.1% a year in the first 12 years (2001 to 2012), and trailed it by 1.0% a year in the 13 after. The biggest gaps are 20.8% in 2009 and 17.7% in 2001.
### That fits survivorship: the early years, where we see half the index, look too good. In 2023 and 2024 the gap is -10.4% and -11.3% while we see almost all the index, so that part comes from the weighting.
### So early years will look better than they really were, and later notebooks report scores per period rather than one number over 25 years.

---
```

## C. A model notebook (ml_model_compare/03_logistic_regression.ipynb)

markdown cell
```markdown
# Logistic Regression
### The model is written from scratch in PyTorch in `self_module/logistic.py` (the maths is in the comments there).
```

markdown cell
```markdown
## 6. Why logistic regression
### It takes a weighted sum of the features and turns it into a probability (0 to 1) with the sigmoid function. The weights are learned with gradient descent.
### Our target is yes / no, so it fits. The probability also lets the bank rank clients and call the most likely ones first.
### Easy to interpret: each weight shows if a feature pushes towards yes or no.
### Limitations: it can only draw a straight line boundary, so non linear patterns (like age) are missed. It also needs scaled features.
```

markdown cell
```markdown
## 7. Training
### Loading the data and adding a column of 1s for the bias.
```

code cell
```python
def load(name):
    X = torch.tensor(pd.read_csv(f'data/X_{name}.csv').values, dtype=torch.float32)
    y = torch.tensor(pd.read_csv(f'data/y_{name}.csv').values, dtype=torch.float32)
    X = torch.cat([X, torch.ones((len(X), 1))], dim=1)
    return X, y

X_train, y_train = load('train')
X_val, y_val = load('val')
X_test, y_test = load('test')
X_train.shape
```

markdown cell
```markdown
### max_lr gives the largest learning rate that is still safe, so no guessing.
```

code cell
```python
model = LogisticRegression()
lr = model.max_lr(X_train)
model = LogisticRegression(lr=lr, epochs=3000)
model.train(X_train, y_train, X_val, y_val, log_every=500);
```

code cell
```python
loss = pd.DataFrame(model.history, columns=['train', 'val'])
fig = px.line(loss, title='Loss')
fig.show()
```

markdown cell
```markdown
### Train and validation loss are almost the same, so it is not overfitting.
```

markdown cell
```markdown
## 8. Evaluation
### 0.5 is the default threshold, but with only 12% yes the model rarely goes above it. Picking the threshold with the best F1 on validation.
```

code cell
```python
p_val = model.forward(X_val).numpy().ravel()
y_val = y_val.numpy().ravel()

thresholds = np.arange(0.05, 0.95, 0.01)
f1s = [f1_score(y_val, p_val >= t) for t in thresholds]
threshold = thresholds[np.argmax(f1s)]
threshold
```

code cell
```python
def scores(y, p, pred):
    return {'accuracy': accuracy_score(y, pred), 'precision': precision_score(y, pred),
            'recall': recall_score(y, pred), 'f1': f1_score(y, pred), 'roc_auc': roc_auc_score(y, p)}

p_train = model.forward(X_train).numpy().ravel()
p_test = model.forward(X_test).numpy().ravel()
y_train, y_test = y_train.numpy().ravel(), y_test.numpy().ravel()

pd.DataFrame({
    'val (0.5)': scores(y_val, p_val, p_val >= 0.5),
    'val': scores(y_val, p_val, p_val >= threshold),
    'train': scores(y_train, p_train, p_train >= threshold),
    'test': scores(y_test, p_test, p_test >= threshold),
}).round(3)
```

markdown cell
```markdown
### With 0.5 the model finds only 18% of the subscribers (recall). The tuned threshold finds about 41%.
### Accuracy is about 0.88, the same as always saying no, which is why it is not a good metric here.
### ROC-AUC is 0.77 (0.5 = random guessing, 1 = perfect).
### Train and test scores are close, so the model generalises well.
```

markdown cell
```markdown
### Simple sklearn implementation
```

code cell
```python
from sklearn.linear_model import LogisticRegression as SkLogisticRegression

sk_model = SkLogisticRegression(C=1e12, max_iter=10000)
sk_model.fit(pd.read_csv('data/X_train.csv'), y_train)
p_sk = sk_model.predict_proba(pd.read_csv('data/X_test.csv'))[:, 1]
```

markdown cell
```markdown
### Our model vs sklearn
```

code cell
```python
pd.DataFrame({
    'our model': scores(y_test, p_test, p_test >= threshold),
    'sklearn': scores(y_test, p_sk, p_sk >= threshold),
}).round(3)
```

markdown cell
```markdown
### Both give almost the same results.
```
