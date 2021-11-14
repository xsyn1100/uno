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


from telegram import ReplyKeyboardMarkup
from telegram.ext import CommandHandler, RegexHandler

from utils import send_async
from user_setting import UserSetting
from shared_vars import dispatcher
from locales import available_locales
from internationalization import _, user_locale


@user_locale
def show_settings(bot, update):
    chat = update.message.chat

    if update.message.chat.type != 'private':
        send_async(bot, chat.id,
                   text=_("Lütfen ayarlarınızı botla özel bir "
                          "sohbette düzenleyin. "))
        return

    us = UserSetting.get(id=update.message.from_user.id)

    if not us:
        us = UserSetting(id=update.message.from_user.id)

    if not us.stats:
        stats = '📈' + ' ' + _("İstatistikleri etkinleştir")
    else:
        stats = '⛔️' + ' ' + _("Tüm istatistikleri sil")

    kb = [[stats], ['🌐' + ' ' + _("Dil")]]
    send_async(bot, chat.id, text='🔧' + ' ' + _("Ayarlar"),
               reply_markup=ReplyKeyboardMarkup(keyboard=kb,
                                                one_time_keyboard=True))


@user_locale
def kb_select(bot, update, groups):
    chat = update.message.chat
    user = update.message.from_user
    option = groups[0]

    if option == '📈':
        us = UserSetting.get(id=user.id)
        us.stats = True
        send_async(bot, chat.id, text=_("İstatistikler Etkinleşti!"))

    elif option == '🌐':
        kb = [[locale + ' - ' + descr]
              for locale, descr
              in sorted(available_locales.items())]
        send_async(bot, chat.id, text=_("Yerel ayar seçin....."),
                   reply_markup=ReplyKeyboardMarkup(keyboard=kb,
                                                    one_time_keyboard=True))

    elif option == '⛔️':
        us = UserSetting.get(id=user.id)
        us.stats = False
        us.first_places = 0
        us.games_played = 0
        us.cards_played = 0
        send_async(bot, chat.id, text=_("Silindi ve istatistikler  devre dışı bırakıldı!"))


@user_locale
def locale_select(bot, update, groups):
    chat = update.message.chat
    user = update.message.from_user
    option = groups[0]

    if option in available_locales:
        us = UserSetting.get(id=user.id)
        us.lang = option
        _.push(option)
        send_async(bot, chat.id, text=_("Yerel ayar yapın!"))
        _.pop()


def register():
    dispatcher.add_handler(CommandHandler('settings', show_settings))
    dispatcher.add_handler(RegexHandler('^([' + '📈' +
                                        '🌐' +
                                        '⛔️' + ']) .+$',
                                        kb_select, pass_groups=True))
    dispatcher.add_handler(RegexHandler(r'^(\w\w_\w\w) - .*',
                                        locale_select, pass_groups=True))
