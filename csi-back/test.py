import asyncio
from app.utils.async_fetch import async_post

text = """\
 Nobody actually talks anymore?
    27 Jan, 2026
I’ve noticed that most conversations don’t really start anymore, they’re triggered.
Someone sends a TikTok. A reel. A screenshot of an Instagram post. We react to the thing, maybe exchange a few lines about it, and then the conversation just dies as soon as the content runs out.
It made me realise how rare it’s become to just… talk. To text about anything and nothing. To rant and rave about something that’s happened in our lives. To just say hello or how you doing without a prompt, or to check in without a goddamn link attached.
I watched a video recently where someone switched to a dumb phone and gave everyone their number. Out of the whole friend group, only one person actually texted it. Everyone else texted their iPhone and just waited for a response instead because what they wanted to send wasn’t a conversation, it was just a piece of content.
And I’ve noticed the same thing in my own life. Conversations that start with something being shown rarely turn into genuine connection. It’s shallow and superficial and once I’ve responded to what I’ve been sent, well… there’s nothing left to say.
It makes me wonder how much of our social lives now are built on sharing things instead of sharing ourselves. We’re always “on”, always reachable, and yet somehow more distant than ever.
Maybe that’s why so many of us feel lonely? Because we’ve replaced talking with… forwarding.
 Previous • Next
"""

async def main():
    response = await async_post(
        "http://192.168.31.51:8001/api/v1/translate/async",
        data={"text": text, "target_lang": "zh"}
    )
    print(response)

if __name__ == "__main__":
    asyncio.run(main())