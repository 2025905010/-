"""Optional Telegram bot for LaLiga match information."""
import os, asyncio
from datetime import timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from services.laliga_api import games, standings, teams, DataUnavailable, now_kst

def team_name(x):
    return x.get("displayName",x.get("name","팀"))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "LaLiga 경기 정보 봇입니다.\n\n"
        "/score - 오늘의 라리가 경기 (한국시간)\n"
        "/ranking - 현재 순위표\n"
        "/teams - 참가 구단 목록\n"
        "/fav <구단명> - 관심 구단 설정\n"
        "/myteam - 관심 구단의 최근/예정 경기\n"
        "예: /fav Real Madrid 또는 /fav Barcelona"
    )

async def score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        rows, stale, saved = await asyncio.to_thread(games, now_kst().date(), 1)
        if not rows:
            await update.message.reply_text("오늘 한국시간 기준 라리가 경기가 없거나 일정 데이터가 없습니다.")
            return
        lines=["라리가 오늘의 경기 (KST)"]
        if stale: lines.append(f"저장 데이터 기준 · {saved:%Y-%m-%d %H:%M}")
        for g in rows[:25]:
            t=g["date"].strftime("%m/%d %H:%M") if g.get("date") else "시간 미정"
            score_text=f'{g["away_score"]}-{g["home_score"]}' if g["state"]!="scheduled" else "VS"
            lines.append(f'{t} | {g["away"]} {score_text} {g["home"]} · {g["status"]}')
        await update.message.reply_text("\n".join(lines)[:3900])
    except DataUnavailable as exc: await update.message.reply_text(str(exc))

async def ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        rows, stale, saved=await asyncio.to_thread(standings)
        lines=["라리가 현재 순위"]
        for row in rows[:30]:
            team=row.get("team",{})
            stats={x.get("name"):x.get("value") for x in row.get("stats",[]) if isinstance(x,dict)}
            lines.append(f'{stats.get("rank","—")}. {team_name(team)} · 승점 {stats.get("points","—")}')
        await update.message.reply_text("\n".join(lines)[:3900])
    except DataUnavailable as exc: await update.message.reply_text(str(exc))

async def list_teams(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        rows,_,_=await asyncio.to_thread(teams)
        await update.message.reply_text("라리가 구단\n"+"\n".join(f"• {team_name(x)}" for x in rows)[:3900])
    except DataUnavailable as exc: await update.message.reply_text(str(exc))

async def fav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name=" ".join(context.args).strip()
    if not name:
        await update.message.reply_text("사용법: /fav Real Madrid")
        return
    context.user_data["favorite"] = name
    await update.message.reply_text(f"관심 구단을 '{name}'으로 설정했습니다. /myteam 으로 일정을 확인하세요.")

async def myteam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name=context.user_data.get("favorite")
    if not name:
        await update.message.reply_text("먼저 /fav <구단명>을 입력하세요.")
        return
    try:
        rows,_,_=await asyncio.to_thread(games, now_kst().date()-timedelta(days=7), 14)
        found=[g for g in rows if name.casefold() in (g["home"]+" "+g["away"]).casefold()]
        if not found:
            await update.message.reply_text(f"'{name}'의 조회 기간 경기 데이터가 없습니다. 구단 이름을 영어로 입력해 보세요.")
            return
        lines=[f"{name} 경기 일정"]
        for g in found[:8]:
            t=g["date"].strftime("%m/%d %H:%M KST") if g.get("date") else "시간 미정"
            score_text=f'{g["away_score"]}-{g["home_score"]}' if g["state"]!="scheduled" else "VS"
            lines.append(f'{t} | {g["away"]} {score_text} {g["home"]}')
        await update.message.reply_text("\n".join(lines)[:3900])
    except DataUnavailable as exc: await update.message.reply_text(str(exc))

def main():
    token=os.getenv("TELEGRAM_BOT_TOKEN","").strip()
    if not token: raise SystemExit("TELEGRAM_BOT_TOKEN 환경변수를 설정하세요.")
    app=ApplicationBuilder().token(token).build()
    for name,fn in [("start",start),("score",score),("ranking",ranking),("teams",list_teams),("fav",fav),("myteam",myteam)]:
        app.add_handler(CommandHandler(name,fn))
    app.run_polling()

if __name__=="__main__": main()
