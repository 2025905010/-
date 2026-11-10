"""LaLiga Korea Dashboard — based on the original six-page sports dashboard.
Run: streamlit run web.py"""
from datetime import timedelta
import pandas as pd
import plotly.express as px
import streamlit as st
from services.laliga_api import DataUnavailable, games, standings, teams, team_details, now_kst
from services.news import get_news

st.set_page_config(page_title="LaLiga | Fútbol Desk", page_icon="⚽", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;600;700&family=Noto+Sans+KR:wght@400;500;700&display=swap');
:root{--ink:#f8fafc;--muted:#cbd5e1;--line:#475569;--accent:#e11d48}
html,body,[class*="css"],.stApp{font-family:'Noto Sans KR',sans-serif}
h1,h2,h3{font-family:'Oswald','Noto Sans KR',sans-serif!important}
.stApp{background-color:#0f172a;background-image:radial-gradient(circle at 50% 0%,#1e293b 0%,#0f172a 60%);color:#f8fafc}
[data-testid="stSidebar"]{background:#111827;border-right:1px solid #334155}
[data-testid="stSidebar"] p,[data-testid="stSidebar"] label,[data-testid="stSidebar"] span{color:#e2e8f0!important}
.block-container{max-width:1370px;padding-top:1.6rem;padding-bottom:4rem}
.hero{padding:28px 32px;background:linear-gradient(135deg,#991b1b 0%,#0f172a 100%);border-left:4px solid #fbbf24;border-radius:12px;margin-bottom:20px}
.hero-title{font-size:2.4rem;font-weight:700;line-height:1.2}
.hero-sub{font-size:1rem;color:#e2e8f0;margin-top:10px}
.kpi{background:#233348;border:1px solid #475569;border-radius:12px;padding:18px;min-height:100px}
.muted{color:#cbd5e1}
.match{background:#233348;border:1px solid #475569;border-radius:12px;padding:15px;margin:8px 0}
</style>
""", unsafe_allow_html=True)

def header(title, subtitle):
    st.markdown(f'<div class="hero"><div class="hero-title">{title}</div><div class="hero-sub">{subtitle}</div></div>', unsafe_allow_html=True)

def show_match(g):
    time_text = g["date"].strftime("%m/%d %H:%M KST") if g.get("date") else "시간 미정"
    if g["state"] == "scheduled":
        score = "VS"
    else:
        score = f'{g["away_score"]} : {g["home_score"]}'
    st.markdown(f"""<div class="match"><div class="muted">{time_text} · {g['status']}</div>
    <h3 style="margin:8px 0">{g['away']} <span style="color:#fbbf24">{score}</span> {g['home']}</h3>
    <div class="muted">🏟️ {g['venue']}</div></div>""", unsafe_allow_html=True)

def load_games(date, days=1):
    try:
        return games(date, days)
    except DataUnavailable as exc:
        st.error(str(exc))
        return [], False, None

def home_page(fav):
    header("LALIGA · FÚTBOL DESK", "스페인 프로축구 라리가의 경기, 구단, 순위와 뉴스를 한곳에서 확인하세요.")
    col1,col2,col3=st.columns(3)
    col1.markdown('<div class="kpi"><b>대회</b><h2>LaLiga EA SPORTS</h2><span class="muted">스페인 1부 리그</span></div>',unsafe_allow_html=True)
    col2.markdown('<div class="kpi"><b>참가 구단</b><h2>20개</h2><span class="muted">시즌별 참가 팀 기준</span></div>',unsafe_allow_html=True)
    col3.markdown('<div class="kpi"><b>시간 기준</b><h2>KST</h2><span class="muted">모든 킥오프 시간은 한국시간</span></div>',unsafe_allow_html=True)
    st.subheader("오늘의 경기")
    gs, stale, saved=load_games(now_kst().date(),1)
    if stale: st.warning(f"저장된 데이터 표시 · 마지막 수집: {saved:%Y-%m-%d %H:%M KST}")
    if gs:
        for g in gs: show_match(g)
    else: st.info("오늘 한국시간 기준으로 표시할 경기가 없거나 일정 데이터를 불러오지 못했습니다.")
    st.subheader("다가오는 경기")
    gs, stale, saved=load_games(now_kst().date(),7)
    if gs:
        for g in gs[:8]: show_match(g)
    st.caption("즐겨찾기 팀: "+fav)

def games_page():
    header("MATCH CENTER", "한국시간 기준으로 라리가 경기 일정과 결과를 확인합니다.")
    date=st.date_input("시작 날짜", value=now_kst().date())
    days=st.slider("조회 기간(일)",1,14,7)
    gs, stale, saved=load_games(date,days)
    if stale: st.warning(f"캐시 데이터 · 마지막 수집: {saved:%Y-%m-%d %H:%M KST}")
    if not gs: st.info("선택한 기간의 경기 데이터가 없습니다.")
    for g in gs: show_match(g)

def standings_page():
    header("LEAGUE TABLE", "라리가 순위표 — API에서 제공하는 현재 시즌 데이터를 표시합니다.")
    try:
        rows, stale, saved=standings()
        if stale: st.warning(f"저장된 데이터 · 마지막 수집: {saved:%Y-%m-%d %H:%M KST}")
        parsed=[]
        for row in rows:
            team=row.get("team",{}) if isinstance(row,dict) else {}
            stats=row.get("stats",[]) if isinstance(row,dict) else []
            s={x.get("name"):x.get("value") for x in stats if isinstance(x,dict)}
            parsed.append({"팀":team.get("displayName",row.get("name","팀")),"순위":s.get("rank","—"),
                "경기":s.get("gamesPlayed","—"),"승":s.get("wins","—"),"무":s.get("ties","—"),
                "패":s.get("losses","—"),"득점":s.get("pointsFor","—"),"실점":s.get("pointsAgainst","—"),
                "승점":s.get("points","—")})
        if parsed:
            df=pd.DataFrame(parsed)
            st.dataframe(df,use_container_width=True,hide_index=True)
            numeric=pd.to_numeric(df["승점"],errors="coerce")
            chart=df.assign(_승점=numeric).dropna(subset=["_승점"])
            if not chart.empty:
                st.subheader("승점 비교")
                st.plotly_chart(px.bar(chart,x="팀",y="_승점",labels={"_승점":"승점"},title="구단별 승점"),use_container_width=True)
        else: st.warning("현재 순위 형식이 제공되지 않았습니다.")
    except DataUnavailable as exc: st.error(str(exc))

def teams_page():
    header("CLUB DIRECTORY", "라리가 참가 구단과 팀 정보를 살펴봅니다.")
    try:
        items, stale, saved=teams()
        options={x.get("displayName",x.get("name","팀")):x for x in items}
        if not options:
            st.info("구단 목록을 가져오지 못했습니다."); return
        selected=st.selectbox("구단 선택",list(options))
        team=options[selected]
        left,right=st.columns([1,2])
        with left:
            if team.get("logo"): st.image(team["logo"],width=140)
            st.subheader(selected)
            st.caption(team.get("abbreviation",""))
        with right:
            st.markdown("### 구단 개요")
            st.write(team.get("nickname","") or "공식 API가 제공하는 기본 구단 정보")
            st.write("연고지/국가:", team.get("location","스페인"))
            st.write("홈페이지:", team.get("links",[{}])[0].get("href","공식 링크 미제공") if team.get("links") else "공식 링크 미제공")
        st.divider()
        st.subheader("전체 구단")
        cols=st.columns(4)
        for i,t in enumerate(items):
            with cols[i%4]:
                if t.get("logo"): st.image(t["logo"],width=55)
                st.caption(t.get("displayName",t.get("name","구단")))
    except DataUnavailable as exc: st.error(str(exc))

def players_page():
    header("PLAYER SPOTLIGHT", "선수 페이지에서는 구단별 선수 명단과 상세 기록을 확인할 수 있습니다.")
    try:
        items,_,_=teams()
        options={x.get("displayName",x.get("name","팀")):x for x in items}
        if not options: st.info("구단 데이터가 없습니다."); return
        selected=st.selectbox("선수 명단을 볼 구단",list(options))
        team=options[selected]
        tid=team.get("id")
        if not tid: st.info("이 구단의 API 식별자가 없습니다."); return
        try:
            data,stale,saved=team_details(tid)
            teamdata=data.get("team",{})
            athletes=teamdata.get("athletes",[])
            if not athletes:
                # ESPN team detail commonly exposes roster via a separate roster endpoint.
                from services.laliga_api import fetch_json
                roster,stale,saved=fetch_json(f"teams/{tid}/roster",ttl=3600)
                athletes=roster.get("athletes",[])
            if athletes:
                rows=[]
                for p in athletes:
                    rows.append({"선수":p.get("fullName",p.get("displayName","선수")),
                                 "포지션":p.get("position",{}).get("displayName","—") if isinstance(p.get("position"),dict) else p.get("position","—"),
                                 "등번호":p.get("jersey","—"),"국적":p.get("flag",{}).get("alt","—") if isinstance(p.get("flag"),dict) else "—"})
                st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
            else:
                st.info("현재 공개 엔드포인트에서 이 구단의 선수 명단을 제공하지 않습니다. 팀 공식 사이트에서 명단을 확인해 주세요.")
        except DataUnavailable as exc: st.warning(str(exc))
    except DataUnavailable as exc: st.error(str(exc))

def stadium_page():
    header("STADIUM GUIDE", "라리가 구단의 홈구장 정보. 구장 세부 자료는 공개 API 제공 범위에 따라 달라집니다.")
    try:
        items,_,_=teams()
        for t in items:
            venue=t.get("venue",{}) or {}
            name=venue.get("fullName") or venue.get("name") or "홈구장 정보 미제공"
            st.markdown(f'<div class="match"><b>{t.get("displayName",t.get("name","구단"))}</b><br><span class="muted">🏟️ {name}</span></div>',unsafe_allow_html=True)
    except DataUnavailable as exc: st.error(str(exc))
    st.caption("수용 인원, 지붕, 피치 치수 등은 API에서 확인되는 경우에만 표시하며 추정값을 넣지 않습니다.")

def news_page():
    header("LATEST NEWS", "라리가 및 스페인 축구 관련 최신 기사.")
    try:
        items,stale,saved=get_news()
        if stale: st.warning(f"저장된 뉴스 · 마지막 수집: {saved:%Y-%m-%d %H:%M KST}")
        if not items: st.info("현재 뉴스 항목을 제공하지 않습니다.")
        for item in items[:25]:
            with st.container(border=True):
                st.subheader(item["title"])
                if item["description"]: st.write(item["description"])
                if item["published"]: st.caption(item["published"])
                if item["url"]: st.link_button("기사 열기",item["url"])
    except DataUnavailable as exc: st.error(str(exc))

def main():
    st.sidebar.title("⚽ FÚTBOL DESK")
    st.sidebar.caption("LaLiga · 스페인 프로축구")
    fav=st.sidebar.selectbox("★ 관심 구단",["레알 마드리드","FC 바르셀로나","아틀레티코 마드리드","아틀레틱 클루브","레알 소시에다드"])
    page=st.sidebar.radio("메뉴",["홈","경기","선수","순위","구단","구장","뉴스"])
    st.sidebar.divider()
    st.sidebar.caption(f"현재 한국시간: {now_kst():%Y-%m-%d %H:%M}")
    st.sidebar.caption("데이터: ESPN 공개 축구 API · 비공식 엔드포인트")
    if st.sidebar.button("캐시 삭제 후 새로고침"):
        for p in ( __import__("pathlib").Path(__file__).parent/"data"/"cache").glob("*.json"):
            p.unlink(missing_ok=True)
        st.rerun()
    if page=="홈": home_page(fav)
    elif page=="경기": games_page()
    elif page=="선수": players_page()
    elif page=="순위": standings_page()
    elif page=="구단": teams_page()
    elif page=="구장": stadium_page()
    elif page=="뉴스": news_page()
    st.divider()
    st.caption("교육용 개인 프로젝트 · 실제 데이터는 공개 ESPN 축구 엔드포인트를 통해 조회합니다. API 제공 범위와 응답은 변경될 수 있습니다.")

if __name__=="__main__": main()
