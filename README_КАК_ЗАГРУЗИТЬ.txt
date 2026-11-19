ARMENIA GUIDE — ФОТО БЕЗ БИТЫХ ССЫЛОК

Причина ошибки: ссылки из предыдущей таблицы на Wikimedia Commons оказались неподтверждёнными, а автоматический поиск в Telegram не восстановил фото.

ЧТО ЗАГРУЗИТЬ В СВОЙ РЕПОЗИТОРИЙ
Откройте https://github.com/vartazaryankaren14/Armenia-guide/upload/main
Распакуйте ZIP. Загрузите index.html, catalog.json, photo-queries.json, photo-verified.json, PHOTO_SOURCES.md и ПАПКИ scripts и .github.
Обязательно сохраните пути папок .github/workflows/photos.yml и scripts/download_photos.py — без них автоматическая загрузка фото не запустится.

На Mac папка .github скрыта. В Finder нажмите Cmd+Shift+. для отображения скрытых файлов.

Нажмите Commit changes.

ПОТОМ ОТКРОЙТЕ:
https://github.com/vartazaryankaren14/Armenia-guide/actions
В списке слева выберите Armenia Guide — скачать фотографии. Если workflow не запустился автоматически, нажмите Run workflow.
Только успешная зелёная галочка в Actions подтверждает, что GitHub сделал загрузку. Результат показан в PHOTO_STATUS.json.

После загрузки фото будут сохранены в images/places. Код обращается сначала к этим файлам в Pages, а если Pages еще не обновил их — к raw.githubusercontent.com.

Если GitHub блокирует Actions или не разрешает запись, откройте Settings → Actions → General, разрешите запуск Actions. При ошибке push проверьте Workflow permissions → Read and write permissions.

ВАЖНО: фотографии загружаются только после запуска GitHub Actions. Этот пакет не содержит фото для 77 мест — он содержит код и скрипт, который должен получить их из Wikimedia Commons на GitHub. Это не гарантирует три изображения для редких мест: если Commons не найдёт подходящих снимков, PHOTO_STATUS.json покажет пропуски.
