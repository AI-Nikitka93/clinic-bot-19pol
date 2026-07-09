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
        
    # Нам нужны строки со 2-й (индекс 1)
    csv_lines = lines[1:]
    # Убираем решетку из заголовка
    if csv_lines[0].startswith('#'):
        csv_lines[0] = csv_lines[0][1:]
    
    # Парсим CSV
    reader = csv.DictReader(csv_lines)
    
    by_servers = []
    ru_servers = []
    
    for row in reader:
        # Проверяем корректность строки
        if not row.get('CountryShort') or not row.get('OpenVPN_ConfigData_Base64'):
            continue
            
        country = row['CountryShort']
        if country == 'BY':
            by_servers.append(row)
        elif country == 'RU':
            ru_servers.append(row)
            
    print(f"Найдено VPN-серверов: Беларусь (BY) - {len(by_servers)}, Россия (RU) - {len(ru_servers)}")
    
    # Приоритет отдаем Беларуси, затем России
    target_server = None
    if by_servers:
        target_server = by_servers[0]
        print(f"Выбран сервер в Беларуси (IP: {target_server['IP']})")
    elif ru_servers:
        target_server = ru_servers[0]
        print(f"Выбран резервный сервер в России (IP: {target_server['IP']})")
        
    if not target_server:
        print("Критическая ошибка: В списке не найдено серверов в BY или RU.")
        sys.exit(1)
        
    # Декодируем и сохраняем конфиг
    try:
        config_base64 = target_server['OpenVPN_ConfigData_Base64']
        config_data = base64.b64decode(config_base64).decode('utf-8')
        
        # Записываем в файл
        with open("client.ovpn", "w", encoding="utf-8") as f:
            f.write(config_data)
            
        print("Успех! Файл конфигурации client.ovpn успешно сохранен.")
    except Exception as e:
        print(f"Ошибка при сохранении конфигурации: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
