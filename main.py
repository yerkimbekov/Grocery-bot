import psycopg2
import telegram
import logging
import time
import os

from datetime import datetime
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, InlineQueryHandler, ConversationHandler, CallbackQueryHandler, CallbackContext, RegexHandler, PrefixHandler
from telegram import InlineQueryResultArticle, InputTextMessageContent, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from config import bot_messages, bot_states, menu
from functools import wraps

DB_Host = os.environ['DB_Host']
DB_Database = os.environ['DB_Database']
DB_User = os.environ['DB_User']
DB_Port = os.environ['DB_Port']
DB_Password = os.environ['DB_Password']

logging.basicConfig(format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                     level = logging.INFO)
                     
logger = logging.getLogger(__name__)
LIST_OF_ADMINS = [251961384, 771840280]
custom_keyboard = [['📋Меню'],
                   ['ℹ️Помощь'],
                   ['✍🏻Отзыв']]

reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard, resize_keyboard = True)
connection = psycopg2.connect(database = DB_Database, user = DB_User, password = DB_Password, host = DB_Host, port = DB_Port)

def build_menu(buttons,
               n_cols,
               header_buttons=None,
               footer_buttons=None):
    menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
    if header_buttons:
        menu.insert(0, [header_buttons])
    if footer_buttons:
        menu.append([footer_buttons])
    return menu

### SQL Functions

def sql_table(connection):
    cur = connection.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS tasks(id BIGSERIAL PRIMARY KEY, user_id integer, amount integer, product_id text)")
    connection.commit()
    cur.close()

def sql_insert(connection, user_id, amount, product_id):
    cur = connection.cursor()
    cur.execute("INSERT INTO tasks(user_id, amount, product_id) VALUES(%s, %s, %s)", (user_id, amount, product_id, ))
    connection.commit()
    cur.close()

def sql_clear(user_id):
    cur = connection.cursor()
    cur.execute("DELETE FROM tasks WHERE user_id = %s", (user_id, ))
    connection.commit()
    cur.close()

def sql_delete(user_id, product_id):
    cur = connection.cursor()
    cur.execute("DELETE FROM tasks WHERE user_id = %s AND product_id = %s", (user_id, product_id, ))
    connection.commit()
    cur.close()

def sql_number_of_products(user_id):
    cur = connection.cursor()
    cur.execute("SELECT COUNT(*) FROM tasks WHERE user_id = %s", (user_id, ))
    number_of_products = cur.fetchall()
    result = number_of_products[0][0]
    connection.commit()
    cur.close()
    return result

def sql_get_products(user_id):
    cur = connection.cursor()
    cur.execute("SELECT product_id, amount FROM tasks WHERE user_id = %s", (user_id, ))
    products = cur.fetchall()
    connection.commit()
    cur.close()
    return products

### Functions

def add_to_database(user_id, amount, product_id):
    sql_insert(connection, user_id, amount, product_id)

def log_text(debug_text):
  print(debug_text)

def send_message(context, chat_id, text):
    try:
        context.bot.send_message(chat_id = chat_id, text = text, reply_markup = reply_markup)
    except:
        log_text('No such chat_id = ' + str(chat_id) + ' using a bot')

def send_message_keyboard(context, chat_id, text, keyboard):
    try:
        context.bot.send_message(chat_id = chat_id, text = text, reply_markup = keyboard)
    except:
        log_text('No such chat_id = ' + str(chat_id) + ' using a bot (kbrd)')

def get_base_inline_keyboard():
    keyboard = [
        [
            InlineKeyboardButton('Овощи 🥦', callback_data = 'vegetables'),
            InlineKeyboardButton('Фрукты 🍏', callback_data = 'fruits'),
        ],
        [
            InlineKeyboardButton('Горячая еда 🍽', callback_data = 'meals'),
            InlineKeyboardButton('Напитки 🥤', callback_data = 'derinks'),
        ],
        [
            InlineKeyboardButton("Отправить заказ администратору 🛎", callback_data = "order")
        ],
        [
            InlineKeyboardButton("Удалить продукт 🗑", callback_data = "delete")
        ],
        [
            InlineKeyboardButton("Очистить корзину 🧺", callback_data = "clear")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_keyboard2(call_data):
    if call_data == "vegetables":
        keyboard = []
        whole_menu = menu.vegetables
        ith = 0
        for i in whole_menu:
            ith = ith + 1
            keyboard.append(InlineKeyboardButton(str(i[0]) + " - " + str(i[1]) + str(i[2]), callback_data = "v" + str(ith)))
    elif call_data == "fruits":
        keyboard = []
        whole_menu = menu.fruits
        ith = 0
        for i in whole_menu:
            ith = ith + 1
            keyboard.append(InlineKeyboardButton(str(i[0]) + " - " + str(i[1]) + str(i[2]), callback_data = "f" + str(ith)))
    elif call_data == "meals":
        keyboard = []
        whole_menu = menu.meals
        ith = 0
        for i in whole_menu:
            ith = ith + 1
            keyboard.append(InlineKeyboardButton(str(i[0]) + " - " + str(i[1]) + str(i[2]), callback_data = "m" + str(ith)))
    elif call_data == "derinks":
        keyboard = []
        whole_menu = menu.derinks
        ith = 0
        for i in whole_menu:
            ith = ith + 1
            keyboard.append(InlineKeyboardButton(str(i[0]) + " - " + str(i[1]) + str(i[2])  , callback_data = "d" + str(ith)))
    keyboard.append(InlineKeyboardButton("⬅️ Назад", callback_data = "back"))
    return InlineKeyboardMarkup(build_menu(keyboard, n_cols = 1))

def get_menu_text(user_id):
    user_products = int(sql_number_of_products(user_id))
    reply_text = str(bot_messages.show_menu_text) + "\n\n"
    if user_products > 0:
        reply_text += bot_messages.show_products_command_response + "\n" + str(get_product_list(user_id))
    else:
        reply_text += bot_messages.products_empty_response
    return str(reply_text)

def get_product_list(user_id):
    ith = 0
    text = ""
    whole_price = 0
    products = sql_get_products(user_id)
    for i in products:
        ith = ith + 1
        decrypted_product = ""
        encrypted = i[0]
        if i[0][0] == 'v':
            x = int(encrypted[1:]) - 1
            decrypted_product = menu.vegetables[x][0] + ": " + str(i[1]) + " * " + str(menu.vegetables[x][1]) + "тг = " + str(int(i[1] * menu.vegetables[x][1])) + "тг"  
            whole_price += int(menu.vegetables[x][1]) * int(i[1])
        elif i[0][0] == 'f':
            x = int(encrypted[1:]) - 1
            decrypted_product = menu.fruits[x][0] + ": " + str(i[1]) + " * " + str(menu.fruits[x][1]) + "тг = " + str(int(i[1] * menu.fruits[x][1])) + "тг"  
            whole_price += int(menu.fruits[x][1]) * int(i[1])
        elif i[0][0] == 'm':
            x = int(encrypted[1:]) - 1
            decrypted_product = menu.meals[x][0] + ": " + str(i[1]) + " * " + str(menu.meals[x][1]) + "тг = " + str(int(i[1] * menu.meals[x][1])) + "тг"  
            whole_price += int(menu.meals[x][1]) * int(i[1])
        elif i[0][0] == 'd':
            x = int(encrypted[1:]) - 1
            decrypted_product = menu.derinks[x][0] + ": " + str(i[1]) + " * " + str(menu.derinks[x][1]) + "тг = " + str(int(i[1] * menu.derinks[x][1])) + "тг"  
            whole_price += int(menu.derinks[x][1]) * int(i[1])
        text = text + str(ith) + ". " + decrypted_product + "\n"
    text = text + "\nИтого: " + str(whole_price) + "тг"
    return str(text)

def show_user_products(user_id):
    user_tasks = sql_number_of_products(user_id)
    reply_text = ""
    if user_tasks > 0:
        reply_text = bot_messages.show_products_command_response + str(get_product_list(user_id))
    else:
        reply_text = bot_messages.products_empty_response
    return reply_text

### Update Functions

def feedback(update, context):
    user_id = update.effective_user.id
    send_message(context, user_id, bot_messages.feedback_write_text)
    return bot_states.READ_FEEDBACK

def read_feedback(update, context):
    text = update.message.text
    user_id = update.effective_user.id
    username = update.message.from_user.username
    text =  "❗️Хей, пользоветель бота отправил новый фидбэк всем админам: ❗️\n\nFeedback:\n" + text + "\n\nUsername: @" + str(username) + "\n\nUser ID: " + str(user_id)
    for admin_id in LIST_OF_ADMINS:
        send_message(context, admin_id, text)
    send_message(context, user_id, bot_messages.feedback_success_command_response)
    return ConversationHandler.END

def check_clear(update, context):
    query = update.callback_query
    user_id = update.effective_user.id
    reply_keyboard = get_base_inline_keyboard()
    user_tasks = sql_number_of_products(user_id)
    if query.data == '1':
        if user_tasks > 0:
            sql_clear(user_id)
        reply_text = "❗️Ваша корзина🧺 успешно очищена.\n\n"
    else:
        reply_text = "❗️Вы успешно отменили очистку корзины🧺.\n\n"
    reply_text += get_menu_text(user_id)
    query.edit_message_text(
        text = reply_text,
        reply_markup = reply_keyboard
    )
    return bot_states.CHECK_MENU

def show_menu(update, context):
    user_id = update.effective_user.id
    reply_keyboard = get_base_inline_keyboard()
    reply_text = get_menu_text(user_id)
    send_message_keyboard(context, user_id, reply_text, reply_keyboard)
    return bot_states.CHECK_MENU

def check_show_menu(update, context):
    query = update.callback_query
    user_id = update.effective_user.id
    data = query.data
    current_text = update.effective_message.text
    if data == "vegetables":
        query.edit_message_text(
            text = current_text,
            reply_markup = get_keyboard2("vegetables")
        )
    elif data == "fruits":
        query.edit_message_text(
            text = current_text,
            reply_markup = get_keyboard2("fruits")
        )      
    elif data == "meals":
        query.edit_message_text(
            text = current_text,
            reply_markup=get_keyboard2("meals")
        )            
    elif data == 'derinks':
        query.edit_message_text(
            text = current_text,
            reply_markup = get_keyboard2("derinks")
        )          
    elif data == "back":
        query.edit_message_text(
            text = current_text,
            reply_markup = get_base_inline_keyboard()
        )
    elif data == "order":
        user_products = sql_number_of_products(user_id)
        if user_products == 0:
            query.edit_message_text(
                text = "❗️Перед тем как отправить ваш заказ, пополните пожалуйста вашу корзину.\n\n" + str(get_menu_text(user_id)),
                reply_markup = get_base_inline_keyboard()
            )
            return bot_states.CHECK_MENU
        else:
            send_message(context, update.effective_user.id, "Хорошо, отправьте пожалуйста ваше ФИО.")
        return bot_states.READ_USER_NAME
    elif data == "delete":
        reply_keyboard = []
        user_tasks = sql_number_of_products(user_id)
        if user_tasks == 0:
            query.edit_message_text(
                text = "❗️Ваша корзина🧺 уже пуста.\n\n" + str(get_menu_text(user_id)),
                reply_markup = get_base_inline_keyboard()
            )
            return bot_states.CHECK_MENU
        query = update.callback_query
        products = sql_get_products(user_id)
        for i in products:
            decrypted_product = ""
            encrypted = i[0]
            if i[0][0] == 'v':
                x = int(encrypted[1:]) - 1
                decrypted_product = menu.vegetables[x][0] + ": " + str(i[1]) + " * " + str(menu.vegetables[x][1]) + "тг = " + str(int(i[1] * menu.vegetables[x][1])) + "тг"  
            elif i[0][0] == 'f':
                x = int(encrypted[1:]) - 1
                decrypted_product = menu.fruits[x][0] + ": " + str(i[1]) + " * " + str(menu.fruits[x][1]) + "тг = " + str(int(i[1] * menu.fruits[x][1])) + "тг"  
            elif i[0][0] == 'm':
                x = int(encrypted[1:]) - 1
                decrypted_product = menu.meals[x][0] + ": " + str(i[1]) + " * " + str(menu.meals[x][1]) + "тг = " + str(int(i[1] * menu.meals[x][1])) + "тг"  
            elif i[0][0] == 'd':
                x = int(encrypted[1:]) - 1
                decrypted_product = menu.derinks[x][0] + ": " + str(i[1]) + " * " + str(menu.derinks[x][1]) + "тг = " + str(int(i[1] * menu.derinks[x][1])) + "тг"  
            reply_keyboard.append(InlineKeyboardButton(decrypted_product, callback_data = str(encrypted)))
        query.edit_message_text(
            text = "Хорошо, выберите продукт который вы хотите удалить из корзины🧺: ",
            reply_markup = InlineKeyboardMarkup(build_menu(reply_keyboard, n_cols = 1))
        )
        return bot_states.CHECK_DELETE
    elif data == "clear":
        keyboard = [
            InlineKeyboardButton("Да", callback_data = '1'),
            InlineKeyboardButton("Нет", callback_data = '2')
        ]
        reply_keyboard = InlineKeyboardMarkup(build_menu(keyboard, n_cols = 1))
        query.edit_message_text(
            text = bot_messages.clear_command_confirmation,
            reply_markup = reply_keyboard
        )
        return bot_states.CHECK_CLEAR
    else:
        query.edit_message_text(
            text = bot_messages.ask_amount_of_products
        )
        context.chat_data['data'] = data
        return bot_states.CHECK_PRODUCT_AMOUNT
    return bot_states.CHECK_MENU

def read_user_name(update, context):
    context.user_data['Name'] = update.message.text
    user_id = update.effective_user.id
    send_message(context, user_id, "Спасибо, теперь для доставки продуктов мне нужен ваш адрес 📍")
    return bot_states.READ_USER_ADDRESS

def read_user_address(update, context):
    context.user_data['Address'] = update.message.text
    user_id = update.effective_user.id
    send_message(context, user_id, "Прекрасно, осталось ввести ваш номер телефона 📱 и я отправлю ваш заказ администраторам.")
    return bot_states.READ_USER_PHONE

def read_user_phone(update, context):
    user_id = update.effective_user.id
    user_phone = 0
    try:
        user_phone = int(update.message.text)
    except:
        send_message(context, user_id, "Введите пожалуйста ваш номер телефона 📱")
        return bot_states.READ_USER_PHONE
    user_name = context.user_data['Name']
    user_address = context.user_data['Address']
    username = update.message.from_user.username
    text =  "❗️Новый заказ от клиента❗️\n\nФИО 👩🏽‍💼👨🏽‍💼: " + str(user_name) + "\nАдрес 📍: " + str(user_address) + "\nНомер телефона 📱: " + str(user_phone) + "\nUsername: @" + str(username) + "\nUser ID: " + str(user_id) + "\n\nЗаказ клиента 🧺: \n" + get_product_list(user_id)
    for admin_id in LIST_OF_ADMINS:
        send_message(context, admin_id, text)
    sql_clear(user_id)
    send_message(context, user_id, bot_messages.order_sent_command_response)
    return ConversationHandler.END

def check_product_amount(update, context):
    user_id = update.effective_user.id
    try:
        amount = int(update.message.text)
        data = context.chat_data['data']
        add_to_database(user_id, amount, data)
        reply_keyboard = get_base_inline_keyboard()
        reply_text = get_menu_text(user_id)
        send_message_keyboard(context, user_id, reply_text, reply_keyboard)
        return bot_states.CHECK_MENU
    except (IndexError, ValueError):
        send_message(context, user_id, bot_messages.amount_is_not_number)
    return ConversationHandler.END

def check_delete(update, context):
    user_id = update.effective_user.id
    query = update.callback_query
    data = query.data
    sql_delete(user_id, data)
    query.edit_message_text (
        text = "❗Данный продукт был успешно удален!\n\n" + get_menu_text(user_id),
        reply_markup = get_base_inline_keyboard()
    )
    return bot_states.CHECK_MENU

def start(update, context):
    context.bot.send_message(chat_id = update.message.chat_id, text = bot_messages.start_command_response, reply_markup = reply_markup)

def help(update, context):
    context.bot.send_message(chat_id = update.message.chat_id, text = bot_messages.help_command_response, reply_markup = reply_markup)

def unknown(update, context):
    context.bot.send_message(chat_id = update.message.chat_id, text = bot_messages.unknown_command_response, reply_markup = reply_markup)

def done(update, context):
    send_message(context, update.effective_user.id, bot_messages.cancelled_successfully)
    return ConversationHandler.END

def main():
    updater = Updater(token = os.environ['BOT_TOKEN'], use_context = True)
    dp = updater.dispatcher
    sql_table(connection)

    start_handler = CommandHandler('start', start)
    help_handler = PrefixHandler('ℹ️', 'Помощь', help)
    show_menu_conv_handler = ConversationHandler(
        entry_points = [PrefixHandler('📋', 'Меню', show_menu)],
        states = {
            bot_states.CHECK_MENU: [CallbackQueryHandler(check_show_menu)],
            bot_states.CHECK_PRODUCT_AMOUNT: [MessageHandler(Filters.text, check_product_amount)],
            bot_states.READ_USER_NAME: [MessageHandler(Filters.text, read_user_name)],
            bot_states.READ_USER_ADDRESS: [MessageHandler(Filters.text, read_user_address)],
            bot_states.READ_USER_PHONE: [MessageHandler(Filters.text, read_user_phone)],
            bot_states.CHECK_CLEAR: [CallbackQueryHandler(check_clear)],
            bot_states.CHECK_DELETE: [CallbackQueryHandler(check_delete)]
        },
        fallbacks = [RegexHandler('[/]*', done)]
    )
    feedback_conv_handler = ConversationHandler(
        entry_points = [PrefixHandler('✍🏻', 'Отзыв', feedback)],
        states = {
            bot_states.READ_FEEDBACK: [MessageHandler(Filters.text, read_feedback)]
        },
        fallbacks = [RegexHandler('[/]*', done)]
    )
    unknown_handler = MessageHandler(Filters.command, unknown)

    dp.add_handler(show_menu_conv_handler)
    dp.add_handler(start_handler)
    dp.add_handler(help_handler)
    dp.add_handler(feedback_conv_handler)
    dp.add_handler(unknown_handler)

    updater.start_polling()
    updater.idle()
if __name__ == '__main__':
    main()
