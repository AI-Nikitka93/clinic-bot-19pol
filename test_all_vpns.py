import requests
import csv
import base64
import subprocess
import time
import os
import sys

def main():
    print("Запрос к API VPNGate...")
    url = "https://www.vpngate.net/api/iphone/"
    try:
        response = requests.get(url, timeout=15)
        response.encoding = 'utf-8'
    except Exception as e:
        print(f"Ошибка API: {e}")
        sys.exit(1)

    lines = response.text.splitlines()
    if len(lines) < 3:
        print("Ошибка: пустой ответ.")
        sys.exit(1)
        
    csv_lines = lines[1:]
    if csv_lines[0].startswith('#'):
        csv_lines[0] = csv_lines[0][1:]
    
    reader = csv.DictReader(csv_lines)
    
    servers = []
    for row in reader:
        if not row.get('CountryShort') or not row.get('OpenVPN_ConfigData_Base64'):
            continue
        country = row['CountryShort']
        if country in ['BY', 'RU']:
            try:
                row['Score'] = int(row.get('Score', 0))
                row['Ping'] = int(row.get('Ping', 9999))
            except ValueError:
                row['Score'] = 0
                row['Ping'] = 9999
            servers.append(row)
            
    # Сортируем: сначала Беларусь, потом Россия по Score
    servers.sort(key=lambda x: (x['CountryShort'] == 'BY', x['Score'], -x['Ping']), reverse=True)
    
    # Берем топ-12 серверов для теста
    # Получаем исходный IP ранера до подключения VPN
    try:
        r_start = requests.get("https://ifconfig.me", timeout=5.0)
        default_ip = r_start.text.strip()
        print(f"Исходный IP ранера: {default_ip}")
    except Exception as e:
        print(f"Не удалось получить исходный IP: {e}")
        default_ip = None

    test_servers = servers[:12]
    print(f"Выбрано {len(test_servers)} серверов для тестирования.")
    
    results = []
    
    for idx, s in enumerate(test_servers):
        ip = s['IP']
        country = s['CountryShort']
        provider = s.get('Operator', 'Unknown')
        print(f"\n[{idx+1}/{len(test_servers)}] Тестирование сервера: {ip} ({country}) - {provider}...")
        
        # Декодируем конфиг
        try:
            config_data = base64.b64decode(s['OpenVPN_ConfigData_Base64']).decode('utf-8')
            with open("temp_client.ovpn", "w", encoding="utf-8") as f:
                f.write(config_data)
        except Exception as e:
            print(f"Ошибка декодирования конфига: {e}")
            continue
            
        # Запускаем openvpn
        log_file = f"openvpn_{ip}.log"
        proc = subprocess.Popen(
            ["sudo", "openvpn", "--config", "temp_client.ovpn", "--auth-user-pass", "auth.txt", "--log", log_file, "--daemon"]
        )
        
        # Ждем поднятия туннеля (до 15 секунд)
        connected = False
        vpn_ip = None
        vpn_country = None
        
        for attempt in range(15):
            time.sleep(1)
            # Проверяем, поднялся ли туннель и изменился ли IP
            try:
                ip_resp = requests.get("https://ifconfig.me", timeout=2.0)
                current_ip = ip_resp.text.strip()
                if default_ip and current_ip == default_ip:
                    # IP еще не изменился
                    continue
                # Для надежности проверим ipinfo
                info_resp = requests.get("https://ipinfo.io/json", timeout=2.0)
                info = info_resp.json()
                vpn_ip = info.get('ip')
                vpn_country = info.get('country')
                connected = True
                print(f"  Подключено! Текущий IP: {vpn_ip} ({vpn_country})")
                break
            except Exception:
                # Еще не поднялся
                pass
                
        if not connected:
            print("  Не удалось подключиться к VPN (таймаут соединения).")
            # Выведем лог openvpn для диагностики
            if os.path.exists(log_file):
                try:
                    log_content = subprocess.check_output(["sudo", "cat", log_file]).decode('utf-8', errors='ignore')
                    print("--- OPENVPN LOG ---")
                    print(log_content[-500:])
                    print("-------------------")
                except Exception as le:
                    print(f"Ошибка чтения лога: {le}")
            # Убиваем процесс
            subprocess.run(["sudo", "killall", "openvpn"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            results.append({"ip": ip, "country": country, "vpn_ip": "Failed", "vpn_country": "", "clinic": "N/A"})
            continue
            
        # Проверяем доступность поликлиники
        clinic_ok = False
        try:
            print("  Проверка связи с поликлиникой self.19crp.by:8028...")
            r = requests.get("http://self.19crp.by:8028/ticket/", timeout=6.0)
            if r.status_code == 200:
                clinic_ok = True
                print("  УСПЕХ! Связь установлена!")
            else:
                print(f"  Ответ поликлиники: {r.status_code}")
        except requests.exceptions.Timeout:
            print("  Таймаут подключения к поликлинике (Порт 8028 заблокирован).")
        except Exception as e:
            print(f"  Ошибка подключения к поликлинике: {e}")
            
        results.append({
            "ip": ip,
            "country": country,
            "vpn_ip": vpn_ip,
            "vpn_country": vpn_country,
            "clinic": "SUCCESS" if clinic_ok else "BLOCKED"
        })
        
        # Отключаем VPN перед следующим тестом
        subprocess.run(["sudo", "killall", "openvpn"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)
        
    print("\n" + "="*50)
    print("ИТОГОВЫЕ РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:")
    print("="*50)
    for r in results:
        print(f"VPN {r['ip']} ({r['country']}) -> Полученный IP: {r['vpn_ip']} ({r['vpn_country']}) | Поликлиника: {r['clinic']}")
    print("="*50)

if __name__ == "__main__":
    main()
