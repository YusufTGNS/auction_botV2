import discord
from discord.ext import commands, tasks
from logic import DatabaseManager, hide_img, create_collage
from config import TOKEN, DATABASE
import os
import cv2

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.members = True  # Kullanıcı rolü değişikliklerini takip edebilmek için

bot = commands.Bot(command_prefix='!', intents=intents)

manager = DatabaseManager(DATABASE)
manager.create_tables()

# Kullanıcı kaydı için bir komut
@bot.command()
async def start(ctx):
    user_id = ctx.author.id
    if user_id in manager.get_users():
        await ctx.send('Zaten kayıtlısınız!')
    else:
        manager.add_user(user_id, ctx.author.name)
        await ctx.send('''Merhaba! Hoş geldiniz! Başarılı bir şekilde kaydoldunuz! Her dakika yeni resimler alacaksınız ve bunları elde etme şansınız olacak! Bunu yapmak için “Al!” butonuna tıklamanız gerekiyor! Sadece “Al!” butonuna tıklayan ilk üç kullanıcı resmi alacaktır! =)''')

# Admin kontrol fonksiyonu (Discord rolünde "Administrator" izni olup olmadığını kontrol eder)
def is_admin(ctx):
    return any(role.permissions.administrator for role in ctx.author.roles)

# Resim göndermek için zamanlanmış bir görev
@tasks.loop(minutes=1)
async def send_message():
    for user_id in manager.get_users():
        prize = manager.get_random_prize()
        if prize is None:
            continue
        prize_id, img = prize[:2]
        hide_img(img)  # Resmi gizle
        user = await bot.fetch_user(user_id)
        if user:
            await send_image(user, f'hidden_img/{img}', prize_id)
        manager.mark_prize_used(prize_id)

async def send_image(user, image_path, prize_id):
    if not os.path.exists(image_path):
        return  # Eğer dosya yoksa, işlem yapma
    with open(image_path, 'rb') as img:
        file = discord.File(img)
        button = discord.ui.Button(label="Al!", custom_id=str(prize_id))
        view = discord.ui.View()
        view.add_item(button)
        await user.send(file=file, view=view)

@bot.command()
async def rating(ctx):
    res = manager.get_rating()
    if not res:
        await ctx.send('Henüz hiçbir sıralama verisi yok.')
        return

    res = [f'| @{x[0]:<11} | {x[1]:<11}|' for x in res]
    res = '\n'.join(res)
    res = f'|USER_NAME    |COUNT_PRIZE|\n{"_"*26}\n' + res
    await ctx.send(f"```\n{res}\n```")

@bot.command()
async def get_my_score(ctx):
    user_id = ctx.author.id
    info = manager.get_winners_img(user_id)
    prizes = [x[0] for x in info]

    if not prizes:
        await ctx.send('Henüz hiç resim kazanmamışsınız!')
        return

    image_paths = os.listdir('img')
    image_paths = [os.path.join('img', x) if x in prizes else os.path.join('hidden_img', x) for x in image_paths]

    collage = create_collage(image_paths)
    collage_path = os.path.join('collages', f'{user_id}_collage.jpg')
    os.makedirs('collages', exist_ok=True)
    cv2.imwrite(collage_path, collage)

    with open(collage_path, 'rb') as img:
        file = discord.File(img)
        await ctx.send(file=file)

# Admin Komutları

@bot.command()
async def admin_add_prize(ctx, image: str):
    # Yalnızca admin komutu (Administrator iznine sahip kullanıcılar için)
    if not is_admin(ctx):
        await ctx.send("Bu komutu kullanma izniniz yok. Lütfen Administrator iznine sahip olun.")
        return
    
    manager.add_prize([(image,)])
    await ctx.send(f"{image} adlı resim başarıyla eklendi.")

@bot.command()
async def admin_set_message_interval(ctx, minutes: int):
    if not is_admin(ctx):
        await ctx.send("Bu komutu kullanma izniniz yok. Lütfen Administrator iznine sahip olun.")
        return

    send_message.change_interval(minutes=minutes)
    await ctx.send(f"Resim gönderme sıklığı {minutes} dakika olarak ayarlandı.")

@bot.command()
async def admin_bonus_points(ctx, user_id: int, points: int):
    if not is_admin(ctx):
        await ctx.send("Bu komutu kullanma izniniz yok. Lütfen Administrator iznine sahip olun.")
        return

    manager.add_bonus_points(user_id, points)
    await ctx.send(f"{points} bonus puan, kullanıcıya başarıyla eklendi.")

@bot.event
async def on_interaction(interaction):
    if interaction.type == discord.InteractionType.component:
        custom_id = interaction.data['custom_id']
        user_id = interaction.user.id

        if manager.get_winners_count(int(custom_id)) < 3:
            res = manager.add_winner(user_id, int(custom_id))
            if res:
                img = manager.get_prize_img(custom_id)
                with open(f'img/{img}', 'rb') as photo:
                    file = discord.File(photo)
                    await interaction.response.send_message(file=file, content="Tebrikler, resmi aldınız!")
            else:
                await interaction.response.send_message(content="Bu resme zaten sahipsiniz!", ephemeral=True)
        else:
            await interaction.response.send_message(content="Maalesef, birisi bu resmi çoktan aldı...", ephemeral=True)

@bot.event
async def on_ready():
    print(f'{bot.user} olarak giriş yapıldı!')
    if not send_message.is_running():
        send_message.start()

bot.run(TOKEN)
