# IRU317 Wi-Fi Recovery Portal

**Русский** | [English](README.en.md)

Небольшой headless Wi-Fi recovery/setup-портал для Ubuntu Server + NetworkManager на машине с **одним Wi-Fi-адаптером**.

Проект появился для мини-ПК iRU 317: сервер должен уметь переезжать между сетями без монитора и клавиатуры. Если знакомая Wi-Fi сеть доступна, NetworkManager подключается к ней как обычно. Если подходящей сети нет, watchdog заранее сканирует эфир, сохраняет список сетей и поднимает аварийную точку доступа `IRU317-SETUP`. Телефон видит captive portal, открывает страницу настройки, пользователь выбирает Wi-Fi и вводит пароль, после чего новый профиль сохраняется для следующих запусков.

## Как это работает

```text
загрузка
  |
  +-- есть сохранённый Wi-Fi --> обычная работа
  |
  +-- сети нет
        |
        +-- несколько проверок watchdog
        +-- сканирование Wi-Fi в client mode
        +-- сохранение списка в /run/iru-wifi-networks.json
        +-- запуск IRU317-SETUP (10.42.0.1/24)
        +-- captive portal на http://10.42.0.1/
        +-- выбор сети + пароль
        +-- сохранение NetworkManager-профиля
        +-- подключение к новой сети
```

Ключевой момент: при одном радиомодуле сканирование выполняется **до** переключения адаптера в AP mode. Поэтому точка настройки не исчезает во время просмотра страницы и портал сразу показывает готовый список сетей.

## Состав

- `scripts/iru-wifi-portal.py` - веб-портал настройки Wi-Fi на Python stdlib, без Flask.
- `scripts/iru-wifi-scan.py` - сканирование и кэширование доступных SSID.
- `scripts/iru-wifi-fallback.sh` - watchdog, который включает setup mode при отсутствии нормального подключения.
- `systemd/iru-wifi-portal.service` - портал.
- `systemd/iru-wifi-fallback.service` + `.timer` - периодическая проверка сети.
- `systemd/iru-captive-redirect.service` - перехват HTTP captive-probe на порт 80.
- `networkmanager/90-iru-captive.conf` - DNS-перенаправление внутри setup-сети.
- `install.sh` - установка файлов и создание безопасного AP-профиля.
- `verify.sh` - неразрушающая проверка, что установленная система совпадает с GitHub-эталоном.

## Требования

Проверенная конфигурация: Ubuntu Server 24.04, NetworkManager 1.46.x, Python 3.12, `iptables`, `dnsmasq`, Wi-Fi адаптер с поддержкой AP mode. Имена интерфейсов в исходной конфигурации: Wi-Fi `wlp1s0`, Ethernet `ens1`.

Проверить поддержку AP можно так:

```bash
sudo iw list | sed -n '/Supported interface modes:/,/Band/p'
```

В списке должен быть `AP`.

## Установка

> Не публикуйте реальные `.nmconnection` файлы: в них могут находиться Wi-Fi PSK.

Клонируйте репозиторий и запустите установщик от root. Пароль setup-сети передаётся только локально и **не записывается в Git**:

```bash
git clone https://github.com/JamesBowie8/iru317-wifi-recovery.git
cd iru317-wifi-recovery
sudo SETUP_PASSWORD='CHANGE-ME-1234' ./install.sh
```

По умолчанию используются:

```text
Wi-Fi interface: wlp1s0
Ethernet:         ens1
Setup SSID:       IRU317-SETUP
Setup address:    10.42.0.1/24
Portal:           http://10.42.0.1/
```

Их можно переопределить переменными окружения.

## Проверка установленной системы по GitHub-эталону

После клонирования репозитория на работающий сервер:

```bash
cd iru317-wifi-recovery
git pull
chmod +x verify.sh
sudo ./verify.sh
```

Скрипт ничего не меняет. Он сравнивает рабочие скрипты, systemd units и dnsmasq-конфиг с файлами из репозитория, проверяет синтаксис, состояние сервисов, параметры `iru-setup`, captive HTTP redirect и наличие зависшего setup-dnsmasq. PSK профиля он не выводит.

Итог без расхождений:

```text
PASS - installed system matches the repository checks.
```

Если рабочий сервер намеренно отличается от репозитория, сначала изучите показанный `diff`; не копируйте изменения в GitHub вслепую.

## Ручная диагностика

```bash
systemctl status iru-wifi-portal --no-pager
systemctl status iru-wifi-fallback.timer --no-pager
systemctl status iru-captive-redirect.service --no-pager
nmcli -f NAME,TYPE,DEVICE connection show --active
sudo /usr/local/sbin/iru-wifi-scan.py
python3 -m json.tool /run/iru-wifi-networks.json
```

## Безопасность и приватность

- Реальные Wi-Fi пароли не должны попадать в репозиторий.
- `IRU317-SETUP` защищён WPA-PSK.
- Портал принимает клиентов только из `10.42.0.0/24` и localhost.
- Новые Wi-Fi профили создаются NetworkManager локально на сервере.
- `.gitignore` исключает `.nmconnection`, секреты, runtime-кэш и локальные бэкапы.
- `verify.sh` проверяет проект без чтения или печати сохранённого Wi-Fi PSK.
- Репозиторий не требует публикации домашних SSID, публичных IP, паролей или `.nmconnection` файлов.

Если используется UFW, разрешите setup-подсети HTTP, DNS и при необходимости аварийный SSH.

## Восстановление доступа

При setup mode локальный адрес сервера - `10.42.0.1`.

## Лицензия

Проект распространяется по лицензии [MIT](LICENSE).
