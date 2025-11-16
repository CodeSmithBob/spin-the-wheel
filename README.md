# Stop and remove everything
docker-compose down -v

# Remove the old image
docker rmi spin-the-wheel-today-web

# Rebuild from scratch
docker-compose up -d --build

# Check logs
docker-compose logs -f



in productions
use volume

# Option 1: Just rebuild (recommended)
docker-compose up -d --build

# Option 2: Stop, then rebuild
docker-compose down         # WITHOUT -v flag
docker-compose up -d --build

To Delete Database Data (fresh start)

# Use the -v flag to remove volumes
docker-compose down -v
docker-compose up -d --build


For Development (on your Mac):

# Make code changes
nano app.py

# Rebuild and restart (keeps data if you have volumes)
docker-compose up -d --build


For Production (on Raspberry Pi):

# Update code
git pull  # or scp files

# Rebuild without losing data
docker-compose up -d --build


The key is: Never use -v flag unless you explicitly want to delete all data. Just docker-compose down or docker-compose up -d --build will preserve your volumes.

Think of it like this:

docker-compose down = Turn off the application (data safe in volumes)

docker-compose down -v = Turn off AND delete all saved data

docker-compose up -d --build = Rebuild code and restart (data stays)

we dont use init_db.py 


# If you ever want to test locally without Docker
python3 init_db.py

# Or initialize a backup database
python3 init_db.py