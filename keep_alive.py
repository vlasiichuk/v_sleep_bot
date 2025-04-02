async def handle(request):
    return web.Response(text="Bot is alive!")

async def start_web_app():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, port=8080)
    await site.start()

def keep_alive():
    asyncio.get_event_loop().create_task(start_web_app())