#!/bin/bash
cd "$(dirname "$0")/.."
echo "Creating database tables..."
source backend/.venv/bin/activate
python -c "
import asyncio
from knot.core.database import init_db
asyncio.run(init_db())
print('Tables created successfully')
"
