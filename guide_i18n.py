"""Переводы страницы «Инструкция» (ключи — русский текст, как в остальном UI)."""

from __future__ import annotations

GUIDE_EN: dict[str, str] = {
    "Инструкция": "User guide",
    "Помощь": "Help",
    "Подробная инструкция по работе с CRM": "Detailed CRM user guide",
    "Простыми словами, без технических терминов.": "In plain language, no technical jargon.",
    "Содержание": "Contents",
    "Что это за программа": "What this app is",
    "Первые шаги": "Getting started",
    "Раздел «Клиенты»": "Clients section",
    "Заказы и оплата": "Orders and payments",
    "Календарь и записи": "Calendar and appointments",
    "Отчёты и цифры": "Reports and numbers",
    "Для владельца бизнеса": "For the business owner",
    "Частые вопросы": "FAQ",
    "Это ваш рабочий блокнот на компьютере: клиенты, записи на приём, кто уже заплатил и кто ещё должен. Всё хранится в одном месте — вы не потеряете переписку и бумажные записи.":
    "This is your business notebook on the computer: clients, appointments, who paid and who still owes you. Everything is in one place.",
    "Вы работаете в браузере (Chrome, Edge, Safari). Ничего устанавливать не нужно — откройте ссылку, которую вам дали, войдите под своим логином и пользуйтесь меню сверху.":
    "You use a browser (Chrome, Edge, Safari). Open your link, sign in, and use the menu at the top.",
    "Войдите с email и паролем, которые указали при регистрации.":
    "Sign in with the email and password you chose at registration.",
    "Язык: справа вверху — RU, EN или CZ. Выбор сохранится.":
    "Language: top right — RU, EN, or CZ.",
    "Выход: кнопка «Выйти» — обязательно нажимайте на чужом компьютере.":
    "Sign out with «Log out» on a shared computer.",
    "После входа откроется раздел «Клиенты» — это главный экран.":
    "After login you see «Clients» — your main screen.",
    "Здесь список всех клиентов: имя, телефон, статус, есть ли долг.":
    "All clients: name, phone, status, debt.",
    "Кнопка добавления клиента — имя обязательно; телефон и email помогут найти человека позже.":
    "Add client — name required; phone and email help you find them.",
    "Поиск и фильтры сверху: по статусу или «только с долгом».":
    "Search and filters: by status or «with debt only».",
    "Нажмите на имя — откроется полная карточка.":
    "Click the name to open the full card.",
    "На одном экране всё о человеке.":
    "Everything about one person on one screen.",
    "Смена статуса (например: Новый → В работе → Завершён).":
    "Change status (e.g. New → In progress → Done).",
    "Комментарии — заметки только для вас, клиент их не видит.":
    "Comments — internal notes only you see.",
    "Напоминания — система покажет на главной, когда пора связаться.":
    "Reminders appear on the main page when due.",
    "Заказы — что вы сделали или продали; цена — сколько клиент должен заплатить.":
    "Orders — work or products; price is what they should pay.",
    "Платежи — деньги, которые уже получили. Долг = заказы минус платежи.":
    "Payments — money received. Debt = orders minus payments.",
    "Записи — визиты в календаре, привязанные к клиенту.":
    "Appointments linked to this client.",
    "Сообщения — если подключены Telegram/WhatsApp, переписка появится здесь.":
    "Messages from Telegram/WhatsApp when connected.",
    "Заказ — это услуга или товар. Платёж — деньги от клиента.":
    "An order is work sold; a payment is money received.",
    "Добавить заказ: название услуги и цена.":
    "Add order: service name and price.",
    "Добавить платёж: сумма и способ (наличные, карта, перевод).":
    "Add payment: amount and method.",
    "В списке видно: «Оплачен», «Не оплачен» или «Частично» — сверяйте перед звонком.":
    "List shows Paid, Unpaid, or Partially.",
    "Редактирование заказа — кнопка с карандашом; можно назначить сотрудника и расходы по заказу.":
    "Edit order — pencil icon; assign staff and order expenses.",
    "Ваше расписание: вид день, неделя или месяц.":
    "Schedule: day, week, or month view.",
    "Новая запись: время, услуга, клиент (можно не выбирать), ответственный сотрудник.":
    "New appointment: time, service, optional client and staff.",
    "Услуга из каталога — длительность и цена подставятся сами.":
    "Catalog service fills duration and price.",
    "Повтор записи — например каждую неделю (до 52 раз).":
    "Recurring appointments up to 52 times.",
    "Отмена — слот остаётся в календаре как отменённый; удаление — убирает совсем.":
    "Cancel keeps slot as cancelled; delete removes it.",
    "Метки вроде «Новый», «Ждёт ответа», «Готово». Свои можно добавить в «Статусы».":
    "Labels like New, Waiting, Done. Add your own in Statuses.",
    "Цвета помогают быстро смотреть таблицу клиентов.":
    "Colors help scan the client table.",
    "Не удаляйте статус, если на нём ещё висят клиенты.":
    "Do not delete a status still in use.",
    "Список ваших услуг с ценой и длительностью в минутах.":
    "Services with price and duration.",
    "Удобно при записи в календаре — меньше печатать.":
    "Used when booking — less typing.",
    "Старые записи сохранят ту цену, что была при создании.":
    "Old appointments keep their original price.",
    "Сообщения из Telegram или WhatsApp, если владелец подключил интеграции.":
    "Messages from Telegram/WhatsApp if the owner connected them.",
    "Ответить можно из карточки клиента, если интеграция работает.":
    "Reply from the client card when integration works.",
    "Если пусто — владельцу нужно настроить «Интеграции» (см. раздел ниже).":
    "If empty — owner must set up Integrations.",
    "Цифры по бизнесу: приход, расходы, чистый результат.":
    "Business numbers: income, expenses, net.",
    "График — последние 12 месяцев.":
    "Chart — last 12 months.",
    "«Скачать CSV» — открыть в Excel для бухгалтера.":
    "Download CSV for Excel.",
    "Сравнение неделя/месяц/год — как дела сейчас по сравнению с прошлым периодом.":
    "Week/month/year comparison.",
    "Люди в команде (это не логины в CRM). Назначаются на заказы и записи.":
    "Team members (not CRM logins). Assigned on orders and appointments.",
    "Укажите имя и должность (мастер, администратор).":
    "Name and role.",
    "Лучше «деактивировать», чем удалять, если человек может вернуться.":
    "Deactivate instead of delete if they may return.",
    "Аренда, реклама, расходники — траты не по одному заказу.":
    "Rent, ads — costs not tied to one order.",
    "Расходы по заказу — на странице редактирования заказа (материалы на эту работу).":
    "Order expenses on the order edit page.",
    "Только тот, кто регистрировал бизнес, видит эти пункты меню.":
    "Only the business registrant sees these menu items.",
    "Интеграции — Telegram-бот, WhatsApp; нужны токены из этих сервисов.":
    "Integrations — Telegram bot, WhatsApp tokens.",
    "Администраторы — отдельные логины для сотрудников, которые видят клиентов, но не меняют интеграции.":
    "Administrators — separate logins for staff.",
    "Храните пароли в секрете; у каждого админа свой email.":
    "Keep passwords safe; each admin has their own email.",
    "Забыли пароль?": "Forgot password?",
    "Спросите владельца бизнеса — он может задать новый пароль администратору. Если вы владелец — зарегистрируйтесь заново только если нет другого выхода.":
    "Ask the business owner for a reset.",
    "Цифры кажутся неправильными?": "Numbers look wrong?",
    "Проверьте, что внесены все платежи. Долг считается автоматически: заказы минус платежи.":
    "Enter all payments. Debt = orders minus payments.",
    "Клиент написал в Telegram, а в CRM пусто?": "Client wrote in Telegram but CRM is empty?",
    "Владельцу проверить «Интеграции» и ссылку webhook (часто нужно обновить после перезапуска интернета).":
    "Owner must check Integrations and webhook URL.",
    "Случайно удалили?": "Deleted by mistake?",
    "Кнопки «отменить» нет — восстановление только из резервной копии базы (спросите того, кто обслуживает сервер).":
    "No undo — only from database backup.",
    "Совет: вносите платежи в тот же день — тогда долг и отчёты всегда актуальны.":
    "Tip: enter payments the same day.",
    "Раздел «Помощь» в верхнем меню — откройте в любой момент.":
    "Open «Help» in the top menu anytime.",
    "После входа откройте «Помощь» в верхнем меню — там пошаговая инструкция.":
    "After sign-in, open «Help» in the top menu.",
    "Карточка клиента": "Client card",
    "Статусы клиентов": "Client statuses",
    "Каталог услуг": "Service catalog",
    "Входящие сообщения": "Inbox messages",
    "Сотрудники": "Staff",
    "Расходы": "Expenses",
}

GUIDE_CZ: dict[str, str] = {
    "Инструкция": "Návod",
    "Помощь": "Nápověda",
    "Подробная инструкция по работе с CRM": "Podrobný návod k CRM",
    "Простыми словами, без технических терминов.": "Jednoduše, bez technických termínů.",
    "Содержание": "Obsah",
    "Что это за программа": "Co je tento program",
    "Первые шаги": "První kroky",
    "Раздел «Клиенты»": "Sekce Klienti",
    "Заказы и оплата": "Objednávky a platby",
    "Календарь и записи": "Kalendář a termíny",
    "Отчёты и цифры": "Reporty a čísla",
    "Для владельца бизнеса": "Pro majitele firmy",
    "Частые вопросы": "Časté dotazy",
    "Это ваш рабочий блокнот на компьютере: клиенты, записи на приём, кто уже заплатил и кто ещё должен. Всё хранится в одном месте — вы не потеряете переписку и бумажные записи.":
    "Váš obchodní zápisník: klienti, termíny, platby a dluhy na jednom místě.",
    "Вы работаете в браузере (Chrome, Edge, Safari). Ничего устанавливать не нужно — откройте ссылку, которую вам дали, войдите под своим логином и пользуйтесь меню сверху.":
    "Pracujete v prohlížeči — odkaz, přihlášení, horní menu.",
    "Войдите с email и паролем, которые указали при регистрации.":
    "Přihlaste se e-mailem a heslem.",
    "Язык: справа вверху — RU, EN или CZ. Выбор сохранится.":
    "Jazyk vpravo nahoře.",
    "Выход: кнопка «Выйти» — обязательно нажимайте на чужом компьютере.":
    "Odhlášení na cizím PC.",
    "После входа откроется раздел «Клиенты» — это главный экран.":
    "Hlavní obrazovka jsou Klienti.",
    "Здесь список всех клиентов: имя, телефон, статус, есть ли долг.":
    "Seznam klientů a dluhů.",
    "Кнопка добавления клиента — имя обязательно; телефон и email помогут найти человека позже.":
    "Přidat klienta — jméno povinné.",
    "Поиск и фильтры сверху: по статусу или «только с долгом».":
    "Filtry podle stavu a dluhu.",
    "Нажмите на имя — откроется полная карточка.":
    "Klik na jméno.",
    "На одном экране всё о человеке.":
    "Vše na jedné kartě.",
    "Смена статуса (например: Новый → В работе → Завершён).":
    "Změna stavu.",
    "Комментарии — заметки только для вас, клиент их не видит.":
    "Interní komentáře.",
    "Напоминания — система покажет на главной, когда пора связаться.":
    "Připomínky na úvodní stránce.",
    "Заказы — что вы сделали или продали; цена — сколько клиент должен заплатить.":
    "Objednávky a ceny.",
    "Платежи — деньги, которые уже получили. Долг = заказы минус платежи.":
    "Platby a výpočet dluhu.",
    "Записи — визиты в календаре, привязанные к клиенту.":
    "Termíny v kalendáři.",
    "Сообщения — если подключены Telegram/WhatsApp, переписка появится здесь.":
    "Zprávy po propojení.",
    "Заказ — это услуга или товар. Платёж — деньги от клиента.":
    "Objednávka vs platba.",
    "Добавить заказ: название услуги и цена.":
    "Přidat objednávku.",
    "Добавить платёж: сумма и способ (наличные, карта, перевод).":
    "Přidat platbu.",
    "В списке видно: «Оплачен», «Не оплачен» или «Частично» — сверяйте перед звонком.":
    "Stav platby.",
    "Редактирование заказа — кнопка с карандашом; можно назначить сотрудника и расходы по заказу.":
    "Úprava objednávky.",
    "Ваше расписание: вид день, неделя или месяц.":
    "Kalendář.",
    "Новая запись: время, услуга, клиент (можно не выбирать), ответственный сотрудник.":
    "Nový termín.",
    "Услуга из каталога — длительность и цена подставятся сами.":
    "Služba z katalogu.",
    "Повтор записи — например каждую неделю (до 52 раз).":
    "Opakování termínů.",
    "Отмена — слот остаётся в календаре как отменённый; удаление — убирает совсем.":
    "Zrušit vs smazat.",
    "Метки вроде «Новый», «Ждёт ответа», «Готово». Свои можно добавить в «Статусы».":
    "Vlastní stavy.",
    "Цвета помогают быстро смотреть таблицу клиентов.":
    "Barvy ve tabulce.",
    "Не удаляйте статус, если на нём ещё висят клиенты.":
    "Nemažte používaný stav.",
    "Список ваших услуг с ценой и длительностью в минутах.":
    "Katalog služeb.",
    "Удобно при записи в календаре — меньше печатать.":
    "Méně psaní při rezervaci.",
    "Старые записи сохранят ту цену, что была при создании.":
    "Staré termíny drží původní cenu.",
    "Сообщения из Telegram или WhatsApp, если владелец подключил интеграции.":
    "Doručené zprávy.",
    "Ответить можно из карточки клиента, если интеграция работает.":
    "Odpověď z karty.",
    "Если пусто — владельцу нужно настроить «Интеграции» (см. раздел ниже).":
    "Prázdné = Integrace.",
    "Цифры по бизнесу: приход, расходы, чистый результат.":
    "Reporty.",
    "График — последние 12 месяцев.":
    "Graf 12 měsíců.",
    "«Скачать CSV» — открыть в Excel для бухгалтера.":
    "CSV export.",
    "Сравнение неделя/месяц/год — как дела сейчас по сравнению с прошлым периодом.":
    "Srovnání období.",
    "Люди в команде (это не логины в CRM). Назначаются на заказы и записи.":
    "Zaměstnanci bez přihlášení.",
    "Укажите имя и должность (мастер, администратор).":
    "Jméno a pozice.",
    "Лучше «деактивировать», чем удалять, если человек может вернуться.":
    "Deaktivovat místo smazání.",
    "Аренда, реклама, расходники — траты не по одному заказу.":
    "Obecné výdaje.",
    "Расходы по заказу — на странице редактирования заказа (материалы на эту работу).":
    "Výdaje k objednávce.",
    "Только тот, кто регистрировал бизнес, видит эти пункты меню.":
    "Jen pro majitele.",
    "Интеграции — Telegram-бот, WhatsApp; нужны токены из этих сервисов.":
    "Integrace Telegram/WhatsApp.",
    "Администраторы — отдельные логины для сотрудников, которые видят клиентов, но не меняют интеграции.":
    "Účty administrátorů.",
    "Храните пароли в секрете; у каждого админа свой email.":
    "Tajná hesla.",
    "Забыли пароль?": "Zapomenuté heslo?",
    "Спросите владельца бизнеса — он может задать новый пароль администратору. Если вы владелец — зарегистрируйтесь заново только если нет другого выхода.":
    "Kontaktujte majitele.",
    "Цифры кажутся неправильными?": "Špatná čísla?",
    "Проверьте, что внесены все платежи. Долг считается автоматически: заказы минус платежи.":
    "Zkontrolujte platby.",
    "Клиент написал в Telegram, а в CRM пусто?": "Zpráva není v CRM?",
    "Владельцу проверить «Интеграции» и ссылку webhook (часто нужно обновить после перезапуска интернета).":
    "Zkontrolovat Integrace.",
    "Случайно удалили?": "Smazáno omylem?",
    "Кнопки «отменить» нет — восстановление только из резервной копии базы (спросите того, кто обслуживает сервер).":
    "Jen ze zálohy.",
    "Совет: вносите платежи в тот же день — тогда долг и отчёты всегда актуальны.":
    "Zadávejte platby tentýž den.",
    "Раздел «Помощь» в верхнем меню — откройте в любой момент.":
    "Nápověda v menu.",
    "После входа откройте «Помощь» в верхнем меню — там пошаговая инструкция.":
    "Po přihlášení — Nápověda.",
    "Карточка клиента": "Karta klienta",
    "Статусы клиентов": "Stavy klientů",
    "Каталог услуг": "Katalog služeb",
    "Входящие сообщения": "Doručené zprávy",
    "Сотрудники": "Zaměstnanci",
    "Расходы": "Výdaje",
}
