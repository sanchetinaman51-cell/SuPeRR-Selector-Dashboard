import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from pathlib import Path

st.set_page_config(page_title='SuPeRR Selector | Pressure Analytics', page_icon='🏏', layout='wide')
ROOT=Path(__file__).parent
DATA=ROOT/'data'

st.markdown('''<style>
.stApp {background: linear-gradient(135deg,#160d2c 0%,#241044 55%,#351044 100%); color:#fff}
[data-testid="stHeader"]{background:transparent}
[data-testid="stSidebar"]{background:#170d2b}
.block-container{padding-top:1.5rem}
.kpi{background:linear-gradient(135deg,#3a1b55,#64204f);padding:18px;border:1px solid #8c4d91;border-radius:14px}
.kpi small{color:#e5c9e9}.kpi h2{margin:0;color:#fff}.hero{padding:22px 26px;border-radius:18px;background:linear-gradient(100deg,#4c1c65,#a52e69);margin-bottom:18px}
.hero h1{margin:0;color:white}.hero p{margin:5px 0 0;color:#f6dced}
[data-testid="stDataFrame"]{background:#fff}
</style>''',unsafe_allow_html=True)

@st.cache_data(show_spinner='Loading ball-by-ball data…')
def load_data():
    bb=pd.read_csv(DATA/'ball_by_ball.csv')
    matches=pd.read_csv(DATA/'matches.csv')
    comps=pd.read_csv(DATA/'competitions.csv')
    for c in ['is_wicket','is_four','is_six']:
        bb[c]=bb[c].astype(str).str.lower().isin(['true','1'])
    for c in ['runs','extras1_runs','extras_2_runs']:
        bb[c]=pd.to_numeric(bb[c],errors='coerce').fillna(0)
    bb['extras_type']=bb['extras_type'].fillna('').astype(str)
    bb['dismissal_type']=bb['dismissal_type'].fillna('').astype(str)
    matches['match_date']=pd.to_datetime(matches['match_date'],errors='coerce')
    matches=matches.merge(comps[['comp_id','season','match_format','comp_name']].drop_duplicates('comp_id'),on='comp_id',how='left')
    return bb,matches

@st.cache_data(show_spinner='Calculating pressure ratings…')
def calculate(bb,matches,season_filter,format_filter):
    m=matches.copy()
    if season_filter!='All': m=m[m.season.astype(str)==season_filter]
    if format_filter!='All': m=m[m.match_format==format_filter]
    ids=set(m.match_id)
    d=bb[bb.match_id.isin(ids)].copy()
    d['total_runs']=d.runs+d.extras1_runs+d.extras_2_runs
    d['legal']=~d.extras_type.str.lower().isin(['wide','overstep','no ball','noball'])
    first=d[d.innings==1].groupby('match_id').agg(first_total=('total_runs','sum')).reset_index()
    mm=m.merge(first,on='match_id',how='inner')
    mm['target']=mm.revised_target.fillna(mm.first_total+1)
    ch=d[d.innings==2].merge(mm[['match_id','target','second_inn_revised_overs']],on='match_id',how='inner')
    ch=ch.sort_values(['match_id','innings_ball_num','over_ball_num']).copy()
    ch['max_legal_balls']=(pd.to_numeric(ch.second_inn_revised_overs,errors='coerce').fillna(20)*6).clip(upper=120)
    ch['legal_before']=ch.groupby('match_id').legal.transform(lambda s:s.cumsum().shift(fill_value=0))
    ch['score_before']=ch.groupby('match_id').total_runs.cumsum()-ch.total_runs
    ch['wkts_before']=ch.groupby('match_id').is_wicket.cumsum()-ch.is_wicket.astype(int)
    ch['balls_left']=(ch.max_legal_balls-ch.legal_before).clip(lower=1)
    ch['runs_needed']=(ch.target-ch.score_before).clip(lower=0)
    ch['rrr']=ch.runs_needed*6/ch.balls_left
    ch['pressure']=(((ch.rrr>=9)|((ch.rrr>=8)&(ch.wkts_before>=4))|((ch.balls_left<=30)&(ch.wkts_before>=3)&(ch.rrr>=7)))&(ch.runs_needed>0))
    ch['batter_ball']=~ch.extras_type.str.lower().eq('wide')
    ch['dismissal_credited']=ch.is_wicket&~ch.dismissal_type.str.lower().isin(['runout','retire out','obstracting the field','obstructing the field'])
    def bat(df,s):
        g=df.groupby('striker_name').agg(balls=('batter_ball','sum'),runs=('runs','sum'),outs=('dismissal_credited','sum'),innings=('match_id','nunique'))
        g['sr']=100*g.runs/g.balls.replace(0,np.nan); g['dr']=100*g.outs/g.balls.replace(0,np.nan)
        return g.add_suffix('_'+s)
    bat=bat(ch[ch.pressure],'p').join(bat(ch[~ch.pressure],'n'),how='left').fillna(0)
    bat['score']=.55*bat.sr_p+.30*(bat.sr_p-bat.sr_n)+.30*(bat.dr_n-bat.dr_p)
    bat=bat[(bat.balls_p>=60)&(bat.innings_p>=8)&(bat.balls_n>=30)].sort_values('score',ascending=False).reset_index()
    ch['bowler_runs']=ch.total_runs-np.where(ch.extras_type.str.lower().isin(['byes','legbyes','penalty']),ch.extras1_runs+ch.extras_2_runs,0)
    ch['bwkt']=ch.is_wicket&ch.dismissal_type.str.lower().isin(['bowled','caught','lbw','stump','hit wicket'])
    ch['bdot']=ch.bowler_runs==0
    def bowl(df,s):
        g=df.groupby('bowler_name').agg(balls=('legal','sum'),runs=('bowler_runs','sum'),wkts=('bwkt','sum'),dots=('bdot','sum'),innings=('match_id','nunique'))
        g['econ']=6*g.runs/g.balls.replace(0,np.nan);g['w6']=6*g.wkts/g.balls.replace(0,np.nan);g['dotpct']=100*g.dots/g.balls.replace(0,np.nan)
        return g.add_suffix('_'+s)
    bowl=bowl(ch[ch.pressure],'p').join(bowl(ch[~ch.pressure],'n'),how='left').fillna(0)
    bowl['score']=-.45*bowl.econ_p+.25*bowl.w6_p*10+.20*(bowl.econ_n-bowl.econ_p)+.10*((bowl.dotpct_p-bowl.dotpct_n)/5)
    bowl=bowl[(bowl.balls_p>=60)&(bowl.innings_p>=8)&(bowl.balls_n>=30)].sort_values('score',ascending=False).reset_index()
    return ch,bat,bowl,m

st.markdown('''<div class="hero"><h1>🏏 SuPeRR Selector</h1><p>Pressure Performance Intelligence Dashboard · IPL & T20I ball-by-ball analysis · 2022 onward</p></div>''',unsafe_allow_html=True)
bb,matches=load_data()
with st.sidebar:
    st.header('🎛️ Dashboard controls')
    seasons=sorted(matches.season.dropna().astype(str).unique())
    season=st.selectbox('Season', ['All']+seasons,index=0)
    formats=['All']+sorted(matches.match_format.dropna().unique().tolist())
    fmt=st.selectbox('Format',formats,index=0)
    st.divider()
    st.caption('Pressure model')
    st.write('Required run rate ≥ 9, or ≥ 8 with at least 4 wickets down, or final 30 balls with ≥ 3 wickets down and RRR ≥ 7.')
    st.caption('Minimum sample: 60 pressure balls, 8 pressure innings and 30 non-pressure balls.')

ch,bat,bowl,filtered_matches=calculate(bb,matches,season,fmt)
# eligibility file is intentionally editable; only explicit unavailable statuses are excluded.
elig_path=ROOT/'player_eligibility.csv'
if not elig_path.exists():
    names=sorted(set(bat.striker_name.dropna().tolist()+bowl.bowler_name.dropna().tolist()))
    pd.DataFrame({'player_name':names,'status':['Needs verification']*len(names),'note':['Verify current IPL availability before final selection']*len(names)}).to_csv(elig_path,index=False)
elig=pd.read_csv(elig_path).drop_duplicates('player_name')
for name in ['Mohit Sharma']:
    if name in set(elig.player_name):
        elig.loc[elig.player_name==name,['status','note']]=['Retired','Retired from all forms of cricket (Dec 2025)']
        elig.to_csv(elig_path,index=False)
exclude=st.sidebar.checkbox('Exclude marked retired / ineligible players',value=True)
def apply_elig(df,col):
    x=df.merge(elig[['player_name','status']],left_on=col,right_on='player_name',how='left')
    x['status']=x.status.fillna('Needs verification')
    if exclude: x=x[~x.status.str.lower().isin(['retired','ineligible','unavailable'])]
    return x.drop(columns=['player_name'])
bat=apply_elig(bat,'striker_name');bowl=apply_elig(bowl,'bowler_name')

matches_n=filtered_matches.match_id.nunique(); balls_n=len(ch); pressure_n=int(ch.pressure.sum()) if len(ch) else 0
c1,c2,c3,c4=st.columns(4)
for col,label,value in [(c1,'Matches analysed',f'{matches_n:,}'),(c2,'Deliveries analysed',f'{balls_n:,}'),(c3,'Pressure deliveries',f'{pressure_n:,}'),(c4,'Qualified batters / bowlers',f'{len(bat)} / {len(bowl)}')]:
    col.markdown(f'<div class="kpi"><small>{label}</small><h2>{value}</h2></div>',unsafe_allow_html=True)

st.subheader('🏆 Pressure rankings')
t1,t2,t3=st.tabs(['Top batters','Top bowlers','Player explorer'])
with t1:
    if len(bat):
        show=bat.head(10).copy(); show.insert(0,'Rank',range(1,len(show)+1))
        st.dataframe(show[['Rank','striker_name','score','runs_p','balls_p','sr_p','sr_n','outs_p','innings_p','status']].rename(columns={'striker_name':'Player','score':'Pressure score','runs_p':'Pressure runs','balls_p':'Pressure balls','sr_p':'Pressure SR','sr_n':'Normal SR','outs_p':'Pressure outs','innings_p':'Pressure innings','status':'Availability status'}),use_container_width=True,hide_index=True)
        fig=px.bar(show.sort_values('score'),x='score',y='striker_name',orientation='h',color='score',color_continuous_scale=['#d18ab3','#f5c45e'],title='Top batters · pressure score')
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',font_color='white',coloraxis_showscale=False)
        st.plotly_chart(fig,use_container_width=True)
    else: st.info('No batters meet the sample-size criteria for this filter.')
with t2:
    if len(bowl):
        show=bowl.head(10).copy();show.insert(0,'Rank',range(1,len(show)+1))
        st.dataframe(show[['Rank','bowler_name','score','wkts_p','balls_p','econ_p','econ_n','dotpct_p','innings_p','status']].rename(columns={'bowler_name':'Player','score':'Pressure score','wkts_p':'Pressure wickets','balls_p':'Pressure balls','econ_p':'Pressure economy','econ_n':'Normal economy','dotpct_p':'Pressure dot %','innings_p':'Pressure innings','status':'Availability status'}),use_container_width=True,hide_index=True)
        fig=px.bar(show.sort_values('score'),x='score',y='bowler_name',orientation='h',color='score',color_continuous_scale=['#d18ab3','#f5c45e'],title='Top bowlers · pressure score')
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',font_color='white',coloraxis_showscale=False)
        st.plotly_chart(fig,use_container_width=True)
    else: st.info('No bowlers meet the sample-size criteria for this filter.')
with t3:
    all_players=sorted(set(ch.striker_name.dropna().unique())|set(ch.bowler_name.dropna().unique()))
    player=st.selectbox('Choose a player',all_players)
    a=ch[(ch.striker_name==player)];b=ch[(ch.bowler_name==player)]
    x,y,z=st.columns(3)
    x.metric('Batting runs',int(a.runs.sum()) if len(a) else 0)
    y.metric('Balls faced',int(a.batter_ball.sum()) if len(a) else 0)
    z.metric('Bowling wickets',int(b.bwkt.sum()) if len(b) else 0)
    if len(a):
        st.write('**Batting split**')
        st.dataframe(a.groupby('pressure').agg(Deliveries=('batter_ball','sum'),Runs=('runs','sum'),Matches=('match_id','nunique')).rename(index={False:'Normal',True:'Pressure'}),use_container_width=True)
    if len(b):
        st.write('**Bowling split**')
        st.dataframe(b.groupby('pressure').agg(Deliveries=('legal','sum'),Runs_conceded=('bowler_runs','sum'),Wickets=('bwkt','sum'),Matches=('match_id','nunique')).rename(index={False:'Normal',True:'Pressure'}),use_container_width=True)

st.divider()
st.subheader('📌 Methodology & interpretation')
st.markdown('''- **Pressure definition:** second-innings chase context using required run rate, wickets lost and balls remaining.
- **Batting score:** combines pressure strike rate, strike-rate change versus normal situations, and dismissal-rate improvement.
- **Bowling score:** rewards lower pressure economy, wicket-taking rate, economy improvement versus normal situations and dot-ball percentage change.
- **Fairness controls:** rankings require minimum pressure and non-pressure samples; filters allow season and format comparisons.
- **Availability:** the supplied historical dataset does not establish current IPL registration/availability for every player. The editable eligibility file excludes only players explicitly marked Retired, Ineligible or Unavailable. Verify every finalist against official current-season records before submission.''')
with st.expander('Edit player eligibility / availability'):
    st.write('Open `player_eligibility.csv` in the dashboard folder. Set status to `Retired`, `Ineligible`, or `Unavailable` to exclude a player; use `Eligible` or `Needs verification` to keep them in rankings.')
    st.download_button('Download eligibility CSV',elig.to_csv(index=False).encode('utf-8'),file_name='player_eligibility.csv',mime='text/csv')
with st.expander('Download ranked results'):
    st.download_button('Download batter rankings CSV',bat.to_csv(index=False).encode('utf-8'),file_name='top_batters.csv',mime='text/csv')
    st.download_button('Download bowler rankings CSV',bowl.to_csv(index=False).encode('utf-8'),file_name='top_bowlers.csv',mime='text/csv')
st.caption('SuPeRR Selector · Built from the supplied competition dataset. Rankings are analytical outputs, not a guarantee of future performance.')
