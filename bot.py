#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Telegram bot to play UNO in group chats
# Copyright (c) 2016 Jannes Höke <uno@jhoeke.de>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import logging
from datetime import datetime

from telegram import ParseMode, InlineKeyboardMarkup, \
    InlineKeyboardButton
from telegram.ext import InlineQueryHandler, ChosenInlineResultHandler, \
    CommandHandler, MessageHandler, Filters, CallbackQueryHandler
from telegram.ext.dispatcher import run_async

import card as c
import settings
import simple_commands
from actions import do_skip, do_play_card, do_draw, do_call_bluff, start_player_countdown
from config import WAITING_TIME, DEFAULT_GAMEMODE, MIN_PLAYERS
from errors import (NoGameInChatError, LobbyClosedError, AlreadyJoinedError,
                    NotEnoughPlayersError, DeckEmptyError)
from internationalization import _, __, user_locale, game_locales
from results import (add_call_bluff, add_choose_color, add_draw, add_gameinfo,
                     add_no_game, add_not_started, add_other_cards, add_pass,
                     add_card, add_mode_classic, add_mode_fast, add_mode_wild, add_mode_text)
from shared_vars import gm, updater, dispatcher
from simple_commands import help_handler
from start_bot import start_bot
from utils import display_name
from utils import send_async, answer_async, error, TIMEOUT, user_is_creator_or_admin, user_is_creator, game_is_running


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

@user_locale
def notify_me(bot, update):
    """Handler for /notify_me command, pm people for next game"""
    chat_id = update.message.chat_id
    if update.message.chat.type == 'private':
        send_async(bot,
                   chat_id,
                   text=_("Bu komutu, bilgilendirilmek için grupda "
                          "yeni bir oyun başladığında gönderin 🔔"))
    else:
        try:
            gm.remind_dict[chat_id].add(update.message.from_user.id)
        except KeyError:
            gm.remind_dict[chat_id] = {update.message.from_user.id}


@user_locale
def new_game(bot, update):
    """Handler for the /new command"""
    chat_id = update.message.chat_id

    if update.message.chat.type == 'private':
        help_handler(bot, update)

    else:

        if update.message.chat_id in gm.remind_dict:
            for user in gm.remind_dict[update.message.chat_id]:
                send_async(bot,
                           user,
                           text=_("Yeni bir oyun başladı {title}").format(
                                title=update.message.chat.title))

            del gm.remind_dict[update.message.chat_id]

        game = gm.new_game(update.message.chat)
        game.starter = update.message.from_user
        game.owner.append(update.message.from_user.id)
        game.mode = DEFAULT_GAMEMODE
        send_async(bot, chat_id,
                   text=_("Yeni oyun oluşturuldu! Oyuna /join ile katıl "
                          "hazır olduğunuzda /start ile başlat 🧩"))


@user_locale
def kill_game(bot, update):
    """Handler for the /kill command"""
    chat = update.message.chat
    user = update.message.from_user
    games = gm.chatid_games.get(chat.id)

    if update.message.chat.type == 'private':
        help_handler(bot, update)
        return

    if not games:
            send_async(bot, chat.id,
                       text=_("Bu sohbette oynanılan UNO oyunu yok."))
            return

    game = games[-1]

    if user_is_creator_or_admin(user, game, bot, chat):

        try:
            gm.end_game(chat, user)
            send_async(bot, chat.id, text=__("Oyun Bitdi❗️", multi=game.translate))

        except NoGameInChatError:
            send_async(bot, chat.id,
                       text=_("Oyun henüz başlamadı. "
                              "Oyuna /join ile katıl sonra /start ile başlat"),
                       reply_to_message_id=update.message.message_id)

    else:
        send_async(bot, chat.id,
                  text=_("Sadece oyun yaratıcısı ({name}) ve yönetici bunu yapabilir.")
                  .format(name=game.starter.first_name),
                  reply_to_message_id=update.message.message_id)

@user_locale
def join_game(bot, update):
    """Handler for the /join command"""
    chat = update.message.chat

    if update.message.chat.type == 'private':
        help_handler(bot, update)
        return

    try:
        gm.join_game(update.message.from_user, chat)

    except LobbyClosedError:
            send_async(bot, chat.id, text=_("Lobi kapatıldı,Kimse Giremez💢"))

    except NoGameInChatError:
        send_async(bot, chat.id,
                   text=_("Şu anda oyun aktif değil 🛑 "
                          "/new komutuyla oyun oluşturun 📣 "),
                   reply_to_message_id=update.message.message_id)

    except AlreadyJoinedError:
        send_async(bot, chat.id,
                   text=_("Oyuna zaten katıldınız.Oyunu /start "
                          "komutuyla başlat 🎯"),
                   reply_to_message_id=update.message.message_id)

    except DeckEmptyError:
        send_async(bot, chat.id,
                   text=_("Destede yeni oyuncuların katılması için  "
                          "yeterli kart kalmadı 🙅🏻"),
                   reply_to_message_id=update.message.message_id)

    else:
        send_async(bot, chat.id,
                   text=_("Oyuna başarıyla katıldı ✅"),
                   reply_to_message_id=update.message.message_id)


@user_locale
def leave_game(bot, update):
    """Handler for the /leave command"""
    chat = update.message.chat
    user = update.message.from_user

    player = gm.player_for_user_in_chat(user, chat)

    if player is None:
        send_async(bot, chat.id, text=_("Bu grupta bir oyunda "
                                        "oynamıyorsunuz."),
                   reply_to_message_id=update.message.message_id)
        return

    game = player.game
    user = update.message.from_user

    try:
        gm.leave_game(user, chat)

    except NoGameInChatError:
        send_async(bot, chat.id, text=_("Bu grupta bir oyunda "
                                        "oynamıyorsunuz."),
                   reply_to_message_id=update.message.message_id)

    except NotEnoughPlayersError:
        gm.end_game(chat, user)
        send_async(bot, chat.id, text=__("Oyun Bitdi❗️", multi=game.translate))

    else:
        if game.started:
            send_async(bot, chat.id,
                       text=__("Tamam. Sonrakı Oyuncu: {name}",
                               multi=game.translate).format(
                           name=display_name(game.current_player.user)),
                       reply_to_message_id=update.message.message_id)
        else:
            send_async(bot, chat.id,
                       text=__("{name} başlamadan önce oyundan ayrıldı.",
                               multi=game.translate).format(
                           name=display_name(user)),
                       reply_to_message_id=update.message.message_id)


@user_locale
def kick_player(bot, update):
    """Handler for the /kick command"""

    if update.message.chat.type == 'private':
        help_handler(bot, update)
        return

    chat = update.message.chat
    user = update.message.from_user

    try:
        game = gm.chatid_games[chat.id][-1]

    except (KeyError, IndexError):
            send_async(bot, chat.id,
                   text=_("Şu anda hiçbir oyun aktif değil. "
                          "/new Komutuyla yeni oyun oluşturun"),
                   reply_to_message_id=update.message.message_id)
            return

    if not game.started:
        send_async(bot, chat.id,
                   text=_("Oyun henüz başlamadı. "
                          "/join ile oyuna katılıp ve /start komutuyla oyunu başlat"),
                   reply_to_message_id=update.message.message_id)
        return

    if user_is_creator_or_admin(user, game, bot, chat):

        if update.message.reply_to_message:
            kicked = update.message.reply_to_message.from_user

            try:
                gm.leave_game(kicked, chat)

            except NoGameInChatError:
                send_async(bot, chat.id, text=_("Oyuncu {name} mevcut oyunda bulunamadı.".format(name=display_name(kicked))),
                                reply_to_message_id=update.message.message_id)
                return

            except NotEnoughPlayersError:
                gm.end_game(chat, user)
                send_async(bot, chat.id,
                                text=_("{0} tarafından tekmelendi {1}".format(display_name(kicked), display_name(user))))
                send_async(bot, chat.id, text=__("Oyun Bitdi❗️", multi=game.translate))
                return

            send_async(bot, chat.id,
                            text=_("{0} tarafından tekmelendi {1}".format(display_name(kicked), display_name(user))))

        else:
            send_async(bot, chat.id,
                text=_("Lütfen tekme atmak istediğiniz kişiye cevap verin ve tekrar /kick yazın."),
                reply_to_message_id=update.message.message_id)
            return

        send_async(bot, chat.id,
                   text=__("Tamam. Sonrakı Oyuncu: {name}",
                           multi=game.translate).format(
                       name=display_name(game.current_player.user)),
                   reply_to_message_id=update.message.message_id)

    else:
        send_async(bot, chat.id,
                  text=_("Sadece oyun yaratıcısı({name}) ve yönetici bunu yapabilir.")
                  .format(name=game.starter.first_name),
                  reply_to_message_id=update.message.message_id)


def select_game(bot, update):
    """Handler for callback queries to select the current game"""

    chat_id = int(update.callback_query.data)
    user_id = update.callback_query.from_user.id
    players = gm.userid_players[user_id]
    for player in players:
        if player.game.chat.id == chat_id:
            gm.userid_current[user_id] = player
            break
    else:
        send_async(bot,
                   update.callback_query.message.chat_id,
                   text=_("Oyun Bulunamadı !"))
        return

    @run_async
    def selected(bot):
        back = [[InlineKeyboardButton(text=_("Gruba geri dön"),
                                      switch_inline_query='')]]
        bot.answerCallbackQuery(update.callback_query.id,
                                text=_("Lütfen seçtiğiniz gruba geçin!"),
                                show_alert=False,
                                timeout=TIMEOUT)

        bot.editMessageText(chat_id=update.callback_query.message.chat_id,
                            message_id=update.callback_query.message.message_id,
                            text=_("Seçilen grup: {group}\n"
                                   "<b>Doğru gruba geçtiğinizden "
                                   "emin olun!</b>").format(
                                group=gm.userid_current[user_id].game.chat.title),
                            reply_markup=InlineKeyboardMarkup(back),
                            parse_mode=ParseMode.HTML,
                            timeout=TIMEOUT)

    selected(bot)


@game_locales
def status_update(bot, update):
    """Remove player from game if user leaves the group"""
    chat = update.message.chat

    if update.message.left_chat_member:
        user = update.message.left_chat_member

        try:
            gm.leave_game(user, chat)
            game = gm.player_for_user_in_chat(user, chat).game

        except NoGameInChatError:
            pass
        except NotEnoughPlayersError:
            gm.end_game(chat, user)
            send_async(bot, chat.id, text=__("Oyun Bitdi❗️",
                                             multi=game.translate))
        else:
            send_async(bot, chat.id, text=__("{name} Oyundan Kaldırdı",
                                             multi=game.translate)
                       .format(name=display_name(user)))


@game_locales
@user_locale
def start_game(bot, update, args, job_queue):
    """Handler for the /start command"""

    if update.message.chat.type != 'private':
        chat = update.message.chat

        try:
            game = gm.chatid_games[chat.id][-1]
        except (KeyError, IndexError):
            send_async(bot, chat.id,
                       text=_("Oyun bu sohbetde yok. "
                              "/new Komutuyla oluşturun"))
            return

        if game.started:
            send_async(bot, chat.id, text=_("Oyun çoktan başladı!!!"))

        elif len(game.players) < MIN_PLAYERS:
            send_async(bot, chat.id,
                       text=__("Başlamadan önce {minplayers} oyuncular oyuna /join ile katılmalıdır "
                              "Sonra oyunu başlat").format(minplayers=MIN_PLAYERS))

        else:
            # Starting a game
            game.start()

            for player in game.players:
                player.draw_first_hand()
            choice = [[InlineKeyboardButton(text=_("Seçimini yap!"), switch_inline_query_current_chat='')]]
            first_message = (
                __("İlk oyuncu: {name}\n"
                   "İnsanların oyuna katılmasını durdurmak için /close kullanın.⛔️",
                   multi=game.translate)
                .format(name=display_name(game.current_player.user)))

            @run_async
            def send_first():
                """Send the first card and player"""

                bot.sendSticker(chat.id,
                                sticker=c.STICKERS[str(game.last_card)],
                                timeout=TIMEOUT)

                bot.sendMessage(chat.id,
                                text=first_message,
                                reply_markup=InlineKeyboardMarkup(choice),
                                timeout=TIMEOUT)

            send_first()
            start_player_countdown(bot, game, job_queue)

    elif len(args) and args[0] == 'select':
        players = gm.userid_players[update.message.from_user.id]

        groups = list()
        for player in players:
            title = player.game.chat.title

            if player is gm.userid_current[update.message.from_user.id]:
                title = '- %s -' % player.game.chat.title

            groups.append(
                [InlineKeyboardButton(text=title,
                                      callback_data=str(player.game.chat.id))]
            )

        send_async(bot, update.message.chat_id,
                   text=_('Lütfen oynamak istediğiniz grubu seçin.'),
                   reply_markup=InlineKeyboardMarkup(groups))

    else:
        help_handler(bot, update)


@user_locale
def close_game(bot, update):
    """Handler for the /close command"""
    chat = update.message.chat
    user = update.message.from_user
    games = gm.chatid_games.get(chat.id)

    if not games:
        send_async(bot, chat.id,
                   text=_("Bu sohbette aktif oyun yok."))
        return

    game = games[-1]

    if user.id in game.owner:
        game.open = False
        send_async(bot, chat.id, text=_("Lobi kapatıldı. "
                                        "Bu oyuna daha fazla oyuncu katılamaz."))
        return

    else:
        send_async(bot, chat.id,
                   text=_("Sadece oyun yaratıcısı ({name}) ve yönetici bunu yapabilir.")
                   .format(name=game.starter.first_name),
                   reply_to_message_id=update.message.message_id)
        return


@user_locale
def open_game(bot, update):
    """Handler for the /open command"""
    chat = update.message.chat
    user = update.message.from_user
    games = gm.chatid_games.get(chat.id)

    if not games:
        send_async(bot, chat.id,
                   text=_("Bu sohbette koşu oyunu yok."))
        return

    game = games[-1]

    if user.id in game.owner:
        game.open = True
        send_async(bot, chat.id, text=_("Lobiyi açıldı. "
                                        "Yeni oyuncular oyuna /join ile katılmalı."))
        return
    else:
        send_async(bot, chat.id,
                   text=_("Sadece oyun yaratıcısı ({name}) ve yönetici bunu yapabilir.")
                   .format(name=game.starter.first_name),
                   reply_to_message_id=update.message.message_id)
        return


@user_locale
def enable_translations(bot, update):
    """Handler for the /enable_translations command"""
    chat = update.message.chat
    user = update.message.from_user
    games = gm.chatid_games.get(chat.id)

    if not games:
        send_async(bot, chat.id,
                   text=_("Bu sohbette aktif oyun yok."))
        return

    game = games[-1]

    if user.id in game.owner:
        game.translate = True
        send_async(bot, chat.id, text=_("Çoklu çeviriler etkinleştirildi. "
                                        "/disable_translations ile devre dışı bırak"))
        return

    else:
        send_async(bot, chat.id,
                   text=_("Sadece oyun yaratıcısı ({name}) ve yönetici bunu yapabilir.")
                   .format(name=game.starter.first_name),
                   reply_to_message_id=update.message.message_id)
        return


@user_locale
def disable_translations(bot, update):
    """Handler for the /disable_translations command"""
    chat = update.message.chat
    user = update.message.from_user
    games = gm.chatid_games.get(chat.id)

    if not games:
        send_async(bot, chat.id,
                   text=_("Bu sohbette aktif oyun yok."))
        return

    game = games[-1]

    if user.id in game.owner:
        game.translate = False
        send_async(bot, chat.id, text=_("Çoklu çeviriler Devre dışı  "
                                        "/enable_translations "
                                        "ile tekrar etkinleştirin"))
        return

    else:
        send_async(bot, chat.id,
                   text=_("Sadece oyun yaratıcısı ({name}) ve yönetici bunu yapabilir.")
                   .format(name=game.starter.first_name),
                   reply_to_message_id=update.message.message_id)
        return


@game_locales
@user_locale
def skip_player(bot, update):
    """Handler for the /skip command"""
    chat = update.message.chat
    user = update.message.from_user

    player = gm.player_for_user_in_chat(user, chat)
    if not player:
        send_async(bot, chat.id,
                   text=_("Bu sohbette bir oyun oynamıyorsunuz."))
        return

    game = player.game
    skipped_player = game.current_player

    started = skipped_player.turn_started
    now = datetime.now()
    delta = (now - started).seconds

    # You can't skip if the current player still has time left
    # You can skip yourself even if you have time left (you'll still draw)
    if delta < skipped_player.waiting_time and player != skipped_player:
        n = skipped_player.waiting_time - delta
        send_async(bot, chat.id,
                   text=_("Lütfen {time} saniye bekleyin",
                          "Lütfen {time} saniye bekleyin",
                          n)
                   .format(time=n),
                   reply_to_message_id=update.message.message_id)
    else:
        do_skip(bot, player)


@game_locales
@user_locale
def reply_to_query(bot, update):
    """
    Handler for inline queries.
    Builds the result list for inline queries and answers to the client.
    """
    results = list()
    switch = None

    try:
        user = update.inline_query.from_user
        user_id = user.id
        players = gm.userid_players[user_id]
        player = gm.userid_current[user_id]
        game = player.game
    except KeyError:
        add_no_game(results)
    else:

        # The game has not started.
        # The creator may change the game mode, other users just get a "game has not started" message.
        if not game.started:
            if user_is_creator(user, game):
                add_mode_classic(results)
                add_mode_fast(results)
                add_mode_wild(results)
                add_mode_text(results)
            else:
                add_not_started(results)


        elif user_id == game.current_player.user.id:
            if game.choosing_color:
                add_choose_color(results, game)
                add_other_cards(player, results, game)
            else:
                if not player.drew:
                    add_draw(player, results)

                else:
                    add_pass(results, game)

                if game.last_card.special == c.DRAW_FOUR and game.draw_counter:
                    add_call_bluff(results, game)

                playable = player.playable_cards()
                added_ids = list()  # Duplicates are not allowed

                for card in sorted(player.cards):
                    add_card(game, card, results,
                             can_play=(card in playable and
                                            str(card) not in added_ids))
                    added_ids.append(str(card))

                add_gameinfo(game, results)

        elif user_id != game.current_player.user.id or not game.started:
            for card in sorted(player.cards):
                add_card(game, card, results, can_play=False)

        else:
            add_gameinfo(game, results)

        for result in results:
            result.id += ':%d' % player.anti_cheat

        if players and game and len(players) > 1:
            switch = _('Şuanki oyun: {game}').format(game=game.chat.title)

    answer_async(bot, update.inline_query.id, results, cache_time=0,
                 switch_pm_text=switch, switch_pm_parameter='select')


@game_locales
@user_locale
def process_result(bot, update, job_queue):
    """
    Handler for chosen inline results.
    Checks the players actions and acts accordingly.
    """
    try:
        user = update.chosen_inline_result.from_user
        player = gm.userid_current[user.id]
        game = player.game
        result_id = update.chosen_inline_result.result_id
        chat = game.chat
    except (KeyError, AttributeError):
        return

    logger.debug("Selected result: " + result_id)

    result_id, anti_cheat = result_id.split(':')
    last_anti_cheat = player.anti_cheat
    player.anti_cheat += 1

    if result_id in ('hand', 'gameinfo', 'nogame'):
        return
    elif result_id.startswith('mode_'):
        # First 5 characters are 'mode_', the rest is the gamemode.
        mode = result_id[5:]
        game.set_mode(mode)
        logger.info("Oyun modu {mode} olarak değiştirildi".format(mode = mode))
        send_async(bot, chat.id, text=__("Oyun modu değiştirildi {mode}".format(mode = mode)))
        return
    elif len(result_id) == 36:  # UUID result
        return
    elif int(anti_cheat) != last_anti_cheat:
        send_async(bot, chat.id,
                   text=__("{name} tarafından hile girişimi!", multi=game.translate)
                   .format(name=display_name(player.user)))
        return
    elif result_id == 'call_bluff':
        reset_waiting_time(bot, player)
        do_call_bluff(bot, player)
    elif result_id == 'draw':
        reset_waiting_time(bot, player)
        do_draw(bot, player)
    elif result_id == 'pass':
        game.turn()
    elif result_id in c.COLORS:
        game.choose_color(result_id)
    else:
        reset_waiting_time(bot, player)
        do_play_card(bot, player, result_id)

    if game_is_running(game):
        nextplayer_message = (
            __("Sonrakı Oyuncu: {name}", multi=game.translate)
            .format(name=display_name(game.current_player.user)))
        choice = [[InlineKeyboardButton(text=_("Seçimini yap!"), switch_inline_query_current_chat='')]]
        send_async(bot, chat.id,
                        text=nextplayer_message,
                        reply_markup=InlineKeyboardMarkup(choice))
        start_player_countdown(bot, game, job_queue)


def reset_waiting_time(bot, player):
    """Resets waiting time for a player and sends a notice to the group"""
    chat = player.game.chat

    if player.waiting_time < WAITING_TIME:
        player.waiting_time = WAITING_TIME
        send_async(bot, chat.id,
                   text=__(" Bekleme süresi {name} için {time} saniyeye "
                           "sıfırlandı", multi=player.game.translate)
                   .format(name=display_name(player.user), time=WAITING_TIME))


# Add all handlers to the dispatcher and run the bot
dispatcher.add_handler(InlineQueryHandler(reply_to_query))
dispatcher.add_handler(ChosenInlineResultHandler(process_result, pass_job_queue=True))
dispatcher.add_handler(CallbackQueryHandler(select_game))
dispatcher.add_handler(CommandHandler('start', start_game, pass_args=True, pass_job_queue=True))
dispatcher.add_handler(CommandHandler('new', new_game))
dispatcher.add_handler(CommandHandler('kill', kill_game))
dispatcher.add_handler(CommandHandler('join', join_game))
dispatcher.add_handler(CommandHandler('leave', leave_game))
dispatcher.add_handler(CommandHandler('kick', kick_player))
dispatcher.add_handler(CommandHandler('open', open_game))
dispatcher.add_handler(CommandHandler('close', close_game))
dispatcher.add_handler(CommandHandler('enable_translations',
                                      enable_translations))
dispatcher.add_handler(CommandHandler('disable_translations',
                                      disable_translations))
dispatcher.add_handler(CommandHandler('skip', skip_player))
dispatcher.add_handler(CommandHandler('notify_me', notify_me))
simple_commands.register()
settings.register()
dispatcher.add_handler(MessageHandler(Filters.status_update, status_update))
dispatcher.add_error_handler(error)

start_bot(updater)
updater.idle()
