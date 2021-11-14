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

from telegram import ParseMode
from telegram.ext import CommandHandler

from user_setting import UserSetting
from utils import send_async
from shared_vars import dispatcher
from internationalization import _, user_locale

@user_locale
def help_handler(bot, update):
    """Handler for the /help command"""
    help_text = _("👋 <b>Merhaba Ben UnoTürkiye Botu. Arkadaşlarınızla Eğlenmeniz İçin Oluşturuldum</b>🤖\n\n<b>Botu Kurmak İçin:</b>👇\n\n"
      "<i>1. Kendi Grubuna Botu Ekle!</i>\n"
      "<i>2. Gruba ekledikten botu yönetici yapın, sonra /new komutuyla oyun oluşturun ve\n/join ile oyuna katılın</i>\n"
      "<i>3. Oyunu minimum 2 kişi ile oynamak mümkündür</i>"
      "<i>Oyuncular oyuna katıldıkdan sonra /start ile oyunu başlatın</i> 📌\n\n"
      "<b>Oyun Komutları:</b>\n"
      "<i>/new - Oyun Oluştur 🏆</i>\n"
      "<i>/join - Oyuna Katıl 🎯</i>\n"
      "<i>/open - Lobiyi Aç ✅</i>\n"
      "<i>/close - Lobiyi Kapat ⛔️</i>\n"
      "<i>/kill - Oyunu Sonlandır❗️</i>\n"
      "<i>/kick - Oyuncuyu Oyundan Tekmele</i> 🦶🏻\n\n"
      "Sorularınız İçin <a href=\"https://t.me/husnuehedov\">"
      "𝙷𝚄̈𝚂𝙽𝚄̈ 𝙴𝙷𝙴𝙳𝙾𝚅 🇦🇿 </a> ")

    send_async(bot, update.message.chat_id, text=help_text,
               parse_mode=ParseMode.HTML, disable_web_page_preview=True)

@user_locale
def modes(bot, update):
    """Handler for the /help command"""
    modes_explanation = _("UNOTürkiye botunun dört oyun modu vardır: Klasik, Hızlı, Vahşi ve Metin.\n\n"
      " 🎻 Klasik mod, geleneksel UNO güvertesini kullanır ve otomatik atlama yoktur.\n"
      " 🚀 Hızlı modu, geleneksel UNO destesini kullanır ve sırasını oynaması çok uzun sürerse, bot bir oyuncuyu otomatik olarak atlar.\n"
      " 🐉 Vahşi modu, daha fazla özel kart, daha az sayı çeşitliliği ve otomatik atlama olmayan bir deste kullanır.\n"
      " ✍️ Metin modu, geleneksel UNO güvertesini kullanır, ancak çıkartmalar yerine metni kullanır..\n\n"
      "Oyun modunu değiştirmek için OYUN OLUŞTURUCU, bot takma adını ve bir boşluk yazmalıdır., "
      "tıpkı bir kart oynarken olduğu gibi ve tüm oyun modu seçenekleri görünmelidir.")
    send_async(bot, update.message.chat_id, text=modes_explanation,
               parse_mode=ParseMode.HTML, disable_web_page_preview=True)

@user_locale
def source(bot, update):
    """Handler for the /help command"""
    source_text = _("Bu bot SoftWare Yazılımdır ve AGPL kapsamında lisanslanmıştır.. "
      "İletişim için : \n"
      "t.me/husnuehedov")
    attributions = _("Atıflar:\n"
      "Logo - @SpikerBey")

    send_async(bot, update.message.chat_id, text=source_text + '\n' +
                                                 attributions,
               parse_mode=ParseMode.HTML, disable_web_page_preview=True)


@user_locale
def news(bot, update):
    """Handler for the /news command"""
    send_async(bot, update.message.chat_id,
               text=_("Duyurular: https://telegram.me/teslagametr"),
               disable_web_page_preview=True)


@user_locale
def stats(bot, update):
    user = update.message.from_user
    us = UserSetting.get(id=user.id)
    if not us or not us.stats:
        send_async(bot, update.message.chat_id,
                   text=_("İstatistikleri etkinleştirmediniz.onları etkinleştirmek için "
                          "botda özel sohbetde /settings komutu kullan "))
    else:
        stats_text = list()

        n = us.games_played
        stats_text.append(
            _("{number} oynanan oyun",
              "{number} oynanan oyunlar",
              n).format(number=n)
        )

        n = us.first_places
        stats_text.append(
            _("{number} ilk yer",
              "{number} ilk yerler",
              n).format(number=n)
        )

        n = us.cards_played
        stats_text.append(
            _("{number} oynanan kart",
              "{number} oynanan kartlar",
              n).format(number=n)
        )

        send_async(bot, update.message.chat_id,
                   text='\n'.join(stats_text))


def register():
    dispatcher.add_handler(CommandHandler('help', help_handler))
    dispatcher.add_handler(CommandHandler('source', source))
    dispatcher.add_handler(CommandHandler('news', news))
    dispatcher.add_handler(CommandHandler('stats', stats))
    dispatcher.add_handler(CommandHandler('modes', modes))
