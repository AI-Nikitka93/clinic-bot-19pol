import requests
import csv
import base64
import sys

def main():
    print("Запрос к API VPNGate для получения списка бесплатных VPN...")
    url = "https://www.vpngate.net/api/iphone/"
    try:
        response = requests.get(url, timeout=15)
        response.encoding = 'utf-8'
    except Exception as e:
        print(f"Ошибка при подключении к API VPNGate: {e}")
        sys.exit(1)

    lines = response.text.splitlines()
    if len(lines) < 3:
        print("Ошибка: пустой ответ от API VPNGate.")
        sys.exit(1)
        
    csv_lines = lines[1:]
    if csv_lines[0].startswith('#'):
        csv_lines[0] = csv_lines[0][1:]
    
    reader = csv.DictReader(csv_lines)
    
    by_servers = []
    for row in reader:
        if not row.get('CountryShort') or not row.get('OpenVPN_ConfigData_Base64'):
            continue
            
        country = row['CountryShort']
        try:
            row['Score'] = int(row.get('Score', 0))
            row['Ping'] = int(row.get('Ping', 9999))
        except ValueError:
            row['Score'] = 0
            row['Ping'] = 9999
            
        if country == 'BY':
            by_servers.append(row)
            
    print(f"Найдено VPN-серверов в Беларуси (BY): {len(by_servers)}")
    
    if not by_servers:
        print("Белорусские серверы в VPNGate отсутствуют в данный момент. Завершение с кодом 10.")
        sys.exit(10)
        
    # Сортируем белорусские серверы по качеству
    by_servers.sort(key=lambda x: (x['Score'], -x['Ping']), reverse=True)
    
    target_server = by_servers[0]
    print(f"Выбран сервер в Беларуси (IP: {target_server['IP']}, Score: {target_server['Score']}, Ping: {target_server['Ping']})")
        
    # Декодируем и сохраняем конфиг
    try:
        config_base64 = target_server['OpenVPN_ConfigData_Base64']
        config_data = base64.b64decode(config_base64).decode('utf-8')
        
        safe_lines = []
        for line in config_data.splitlines():
            clean_line = line.strip().lower()
            if clean_line.startswith(("up ", "down ", "route-up ", "script-security ", "command ")):
                continue
            safe_lines.append(line)
        
        with open("client.ovpn", "w", encoding="utf-8") as f:
            f.write("\n".join(safe_lines))
            
        print("Успех! Файл конфигурации client.ovpn успешно сохранен.")
        sys.exit(0)
    except Exception as e:
        print(f"Ошибка при сохранении конфигурации: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
