# Stand-Up Meeting Task Manager

A production-ready Flask application for managing stand-up meeting tasks with **PostgreSQL-only backend**, optimized for Railway deployment.

## 🚀 Features

- ✅ **PostgreSQL Database**: Production-ready database backend
- ✅ **Railway Compatible**: Optimized for Railway cloud deployment
- ✅ **Health Checks**: Built-in health monitoring endpoints
- ✅ **Task Management**: Full CRUD operations for tasks
- ✅ **Analytics Dashboard**: Comprehensive reporting and metrics
- ✅ **Custom Fields**: Extensible task properties
- ✅ **Action Plans**: Stand-up meeting action tracking
- ✅ **CSV Import/Export**: Data portability features

## 🗄️ Database Migration

### From Excel to PostgreSQL

The application has been migrated from Excel-based storage to PostgreSQL with **no fallback mechanisms**:

1. **PostgreSQL Only**: The app uses PostgreSQL exclusively - no Excel fallbacks
2. **Data Migration**: All existing Excel data can be migrated to PostgreSQL using the migration script
3. **Clean Architecture**: Simplified codebase with single data source

### Running the Migration

```bash
# Install dependencies
pip install -r requirements.txt

# Run migration script
python migrate_excel_to_postgres.py
```

## 🏗️ Local Development

### Prerequisites

- Python 3.11+
- PostgreSQL (for production) or SQLite (for development)

### Setup

1. **Clone and install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Environment Configuration:**
   ```bash
   # Copy environment template
   cp env_example.txt .env

   # Edit .env with your settings
   nano .env
   ```

3. **Database Setup:**
   ```bash
   # For local PostgreSQL
   export DATABASE_URL="postgresql://username:password@localhost:5432/tasks_db"

   # Or use SQLite for development
   export DATABASE_URL="sqlite:///tasks.db"
   ```

4. **Run the application:**
   ```bash
   python app.py
   ```

   Or with Gunicorn for production testing:
   ```bash
   gunicorn wsgi:app --bind 0.0.0.0:5000 --workers 1
   ```

## 🚂 Railway Deployment

### Prerequisites

- Railway account
- PostgreSQL database provisioned in Railway

### Deployment Steps

1. **Connect Repository:**
   - Connect your GitHub repository to Railway
   - Railway will automatically detect Python application

2. **Environment Variables:**
   Railway automatically provides `DATABASE_URL`. Add any additional variables:

   ```
   SECRET_KEY=your-production-secret-key
   FLASK_ENV=production
   ```

3. **Database Migration:**
   After deployment, run the migration script:

   ```bash
   railway run python migrate_excel_to_postgres.py
   ```

4. **Health Check:**
   Visit `https://your-app.railway.app/health` to verify deployment

### Railway Configuration Files

- **`Procfile`**: Defines the web process for Railway
- **`runtime.txt`**: Specifies Python version (3.11)
- **`requirements.txt`**: Python dependencies

## 📊 Database Schema

### Tasks Table
- `id`: Primary key (T001, T002, etc.)
- `type`: Task type (Bug, Feature, Task)
- `product`: Product name
- `module`: Module name
- `description`: Task description
- `status`: Current status
- `priority`: Priority level
- `created_date`: Creation date
- `due_date`: Due date
- `current_action_plan`: Current action plan
- `action_plan_history`: Historical action plans
- `custom_fields`: JSON field for custom columns

### App Settings Table
- `key`: Setting name
- `value`: Setting value (JSON)

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | SQLite fallback |
| `SECRET_KEY` | Flask secret key | dev-secret-key |
| `FLASK_ENV` | Environment (development/production) | development |
| `PORT` | Server port | 5000 |

### Database Connection

The app uses SQLAlchemy with connection pooling and automatic reconnection:

- **Pool Pre-ping**: Tests connections before use
- **Pool Recycle**: Recycles connections every 5 minutes
- **Max Overflow**: Handles connection spikes gracefully

## 🛠️ API Endpoints

### Core Endpoints
- `GET /`: Main dashboard
- `POST /add_task`: Add new task
- `POST /edit_task`: Update task
- `POST /delete_task`: Delete task (soft delete)
- `GET /analytics`: Analytics dashboard

### Action Plans
- `POST /update_action_plan`: Update current action plan
- `POST /standup_update_action_plan`: Stand-up meeting update

### Data Management
- `GET /export_csv`: Export tasks to CSV
- `POST /import_csv`: Import tasks from CSV
- `GET /health`: Health check endpoint

### Settings
- `GET /settings`: Get application settings
- `POST /settings`: Update application settings

## 🔍 Troubleshooting

### Network Issues (Railway Deployment)

The previous deployment failure was likely due to:

1. **File System Access**: Excel files don't work on Railway's ephemeral filesystem
2. **Database Connection**: Missing DATABASE_URL or incorrect configuration
3. **Port Binding**: Not binding to 0.0.0.0:$PORT

### Solutions Implemented

- ✅ **Database Backend**: Migrated to PostgreSQL
- ✅ **Environment Config**: Proper Railway environment handling
- ✅ **Health Checks**: Monitoring endpoints
- ✅ **Connection Pooling**: Robust database connections
- ✅ **Error Handling**: Comprehensive fallback mechanisms

### Common Issues

1. **Database Connection Failed:**
   ```bash
   # Check Railway logs
   railway logs

   # Verify DATABASE_URL
   railway variables
   ```

2. **Migration Issues:**
   ```bash
   # Run migration with verbose output
   railway run python migrate_excel_to_postgres.py
   ```

3. **Port Issues:**
   - Railway provides `$PORT` environment variable
   - App automatically uses this port

## 📈 Performance Optimizations

- **Database Indexing**: Optimized queries with proper indexing
- **Connection Pooling**: Efficient database connection management
- **Lazy Loading**: Optimized data loading patterns
- **Caching**: Settings and configuration caching

## 🔐 Security Features

- **Environment Variables**: Sensitive data stored securely
- **SQL Injection Protection**: Parameterized queries
- **CSRF Protection**: Flask-WTF integration ready
- **Secure Headers**: Production-ready headers

## 📝 Development Notes

### Code Structure
```
├── app.py              # Main Flask application
├── models.py           # Database models
├── config.py           # Configuration management
├── wsgi.py             # Production WSGI entry point
├── migrate_excel_to_postgres.py  # Migration script
├── requirements.txt    # Python dependencies
├── Procfile           # Railway process definition
├── runtime.txt        # Python version specification
└── templates/         # HTML templates
```

### Key Improvements Made

1. **PostgreSQL Only**: Complete removal of Excel dependencies and fallbacks
2. **Railway Compatibility**: Optimized for Railway deployment
3. **Simplified Architecture**: Clean, single-backend codebase
4. **Production Ready**: Gunicorn, health checks, proper logging
5. **Environment Management**: Secure configuration management

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License.
