"""PSDA 774 | NESO 2025 decision-focused electricity dashboard."""
from pathlib import Path
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title='PSDA 774 | GB Embedded Renewables', page_icon='⚡', layout='wide')
COLS = ['ND', 'EMBEDDED_WIND_GENERATION', 'EMBEDDED_SOLAR_GENERATION']
@st.cache_data
def load_data():
    path = Path(__file__).with_name('demanddata_2025.csv')
    raw = pd.read_csv(path)
    raw['date'] = pd.to_datetime(raw['SETTLEMENT_DATE'], errors='coerce')
    for c in COLS + ['SETTLEMENT_PERIOD']:
        raw[c] = pd.to_numeric(raw[c], errors='coerce')
    invalid = raw['date'].isna() | raw[COLS].isna().any(axis=1) | (raw['ND'] <= 0) | (raw['EMBEDDED_WIND_GENERATION'] < 0) | (raw['EMBEDDED_SOLAR_GENERATION'] < 0)
    clean = raw.loc[~invalid].copy()
    clean['embedded_mw'] = clean['EMBEDDED_WIND_GENERATION'] + clean['EMBEDDED_SOLAR_GENERATION']
    clean['ratio_pct'] = 100 * clean['embedded_mw'] / clean['ND']
    clean['month'] = clean['date'].dt.month
    clean['month_name'] = clean['date'].dt.strftime('%b')
    clean['period_hour'] = (clean['SETTLEMENT_PERIOD'] - 1) / 2
    return raw, clean, int(invalid.sum())
raw, data, removed = load_data()
st.title('⚡ When is embedded renewable output low relative to electricity demand?')
st.caption('Great Britain · NESO Historic Demand Data 2025 · Half-hourly measurements · PSDA 774')
st.info('Decision indicator: embedded wind + embedded solar / National Demand (ND). This is NOT the total renewable share of GB electricity, and the quantities have different accounting boundaries.')
with st.sidebar:
    st.header('Explore the data')
    dates = st.date_input('Date range', value=(data.date.min().date(), data.date.max().date()), min_value=data.date.min().date(), max_value=data.date.max().date())
    months = st.multiselect('Months', list(range(1,13)), default=list(range(1,13)), format_func=lambda x: pd.Timestamp(2025,x,1).strftime('%b'))
    threshold = st.slider('Low-ratio threshold (%)', 1, 50, 10)
    st.caption('Select a date range and months; all plots and indicators update.')
if isinstance(dates, (tuple, list)) and len(dates)==2:
    start,end=dates
else:
    start,end=data.date.min().date(),data.date.max().date()
f = data.loc[data.date.dt.date.between(start,end) & data.month.isin(months)].copy()
if f.empty:
    st.warning('No observations match the filters. Adjust the date range or months.'); st.stop()
low = f.ratio_pct < threshold
c1,c2,c3,c4=st.columns(4)
c1.metric('Average demand', f'{f.ND.mean()/1000:.2f} GW')
c2.metric('Peak demand', f'{f.ND.max()/1000:.2f} GW')
c3.metric('Mean interval ratio', f'{f.ratio_pct.mean():.1f}%')
c4.metric(f'Intervals below {threshold}%', f'{low.sum():,} ({low.mean()*100:.1f}%)')
st.subheader('1 · When are low-ratio intervals most common?')
by_month=f.assign(low=low).groupby('month',as_index=False).agg(low_fraction=('low','mean'),n=('low','size'))
by_month['low_pct']=100*by_month.low_fraction
fig=px.bar(by_month,x='month',y='low_pct',custom_data=['n'],labels={'month':'Month of 2025','low_pct':'Intervals below threshold (%)'},title='Share of observed intervals below the selected threshold')
fig.update_traces(hovertemplate='Month %{x}<br>Low-ratio intervals: %{y:.1f}%<br>Observed intervals: %{customdata[0]}<extra></extra>')
fig.update_xaxes(tickmode='array',tickvals=list(range(1,13)),ticktext=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'])
fig.update_yaxes(range=[0,100]);fig.update_layout(template='plotly_white')
st.plotly_chart(fig,use_container_width=True)
st.caption('Percentages use the number of valid observations in each selected month as denominator.')
st.subheader('2 · Seasonal demand and embedded generation')
m=f.groupby('month',as_index=False)[COLS].mean()
fig=go.Figure()
for col,label in [('ND','National demand'),('EMBEDDED_WIND_GENERATION','Embedded wind'),('EMBEDDED_SOLAR_GENERATION','Embedded solar')]:
    fig.add_scatter(x=m.month,y=m[col]/1000,mode='lines+markers',name=label)
fig.update_layout(template='plotly_white',xaxis_title='Month of 2025',yaxis_title='Mean power (GW)',legend_title='',hovermode='x unified')
fig.update_xaxes(tickmode='array',tickvals=list(range(1,13)),ticktext=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'])
st.plotly_chart(fig,use_container_width=True)
st.subheader('3 · Typical settlement-period profile')
profile=f.loc[f.SETTLEMENT_PERIOD.between(1,48)].groupby('period_hour',as_index=False)[COLS].mean()
fig=go.Figure()
for col,label in [('ND','National demand'),('EMBEDDED_WIND_GENERATION','Embedded wind'),('EMBEDDED_SOLAR_GENERATION','Embedded solar')]:
    fig.add_scatter(x=profile.period_hour,y=profile[col]/1000,name=label,mode='lines')
fig.update_layout(template='plotly_white',xaxis_title='Settlement-period position (hours; not DST-adjusted civil time)',yaxis_title='Mean power (GW)',hovermode='x unified')
st.plotly_chart(fig,use_container_width=True)
st.subheader('4 · Distribution of embedded generation / demand')
fig=px.histogram(f,x='ratio_pct',nbins=55,labels={'ratio_pct':'Embedded generation / ND (%)'},title='Half-hourly ratio distribution')
fig.add_vline(x=threshold,line_dash='dash',annotation_text=f'{threshold}% threshold')
fig.update_layout(template='plotly_white',yaxis_title='Half-hourly intervals')
st.plotly_chart(fig,use_container_width=True)
with st.expander('Data quality, definitions and limitations'):
    st.write(f'Original records: {len(raw):,}; excluded for invalid date, missing key measurements, non-positive demand or negative embedded generation: {removed:,}; remaining: {len(data):,}.')
    st.write('2025 has 17,520 settlement periods, including daylight-saving days with 46 and 50 settlement periods. For the typical profile, periods 1–48 are used; this is a settlement-period-position approximation, not an exact clock-time alignment.')
    st.write('The ratio is calculated for each half-hourly interval and averaged where shown. It must not be described as the percentage of electricity supplied by all renewable generators. The chart may include ratios exceeding 100% because of measurement/accounting boundaries; these require careful interpretation.')
    st.write('Source: NESO Historic Demand Data 2025. National Demand and embedded wind/solar definitions follow the source metadata. No forecasting model is trained (PSDA 774).')
st.download_button('Download filtered observations (CSV)',f[['date','SETTLEMENT_PERIOD']+COLS+['embedded_mw','ratio_pct']].to_csv(index=False).encode('utf-8'),'psda774_filtered.csv','text/csv')
st.caption('Prepared for the PSDA 774 final project. Source: NESO Historic Demand Data 2025. Analytical use only.')
