# 🖨️ PrintHub - Kabale University Printing Service

> Upload documents, pay with MTN/Airtel mobile money, and pick up prints at campus stations.

[![Django CI](https://github.com/ahumuzaJohnbaptist5/print_hub/actions/workflows/django-ci.yml/badge.svg)](https://github.com/ahumuzaJohnbaptist5/print_hub/actions/workflows/django-ci.yml)
[![Frontend CI](https://github.com/ahumuzaJohnbaptist5/print_hub/actions/workflows/frontend-ci.yml/badge.svg)](https://github.com/ahumuzaJohnbaptist5/print_hub/actions/workflows/frontend-ci.yml)
[![Python Version](https://img.shields.io/badge/python-3.12-blue.svg)](https://python.org)
[![Django Version](https://img.shields.io/badge/django-5.1-green.svg)](https://djangoproject.com)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## ✨ Features

### 🎯 Core Features
- **Document Upload** - PDF, DOCX, PPTX, TXT, images supported
- **Auto Page Detection** - Intelligent page count detection
- **Live Price Calculator** - Real-time pricing with color/double-sided options
- **Multiple Order Types** - Documents, Passport Photos, Scanned Documents
- **Passport Photo Studio** - Live camera capture with background replacement
- **Scanner Mode** - Document scanning with enhancement

### 💳 Payment System
- **MTN Mobile Money** - Copy & Pay with transaction verification
- **Airtel Money** - Full Airtel support
- **Admin Approval Workflow** - Manual verification for security
- **Transaction ID Extraction** - Auto-extract from SMS
- **Payment History** - Full transaction history
- **Saved Payment Methods** - Reuse saved numbers

### 🤖 WhatsApp Bot
- **Order Creation** - Place orders via chat
- **Order Tracking** - Real-time status updates
- **Admin Commands** - Revenue, active orders, approvals
- **Agent Commands** - Earnings, station orders, status updates
- **Group Support** - Advert broadcasts to groups
- **File Uploads** - Send documents via WhatsApp

### 📊 Admin Dashboard
- **Order Management** - Full CRUD with bulk actions
- **Agent Management** - Assign stations to agents
- **Financial Dashboard** - Revenue, costs, profit analytics
- **Paper Inventory** - Track stock levels with alerts
- **Commission Management** - Configure agent commissions
- **Discount Codes** - Create and manage promotions

### 📱 User Features
- **Order Tracking** - Real-time status with timeline
- **Receipts** - Printable, shareable PDF receipts
- **Push Notifications** - Real-time order updates
- **Dark/Light Theme** - User preference saved
- **PWA Support** - Install as mobile app
- **Live Board** - Full-screen order display

## 🚀 Quick Start

### Local Development

```bash
# 1. Clone the repository
git clone https://github.com/ahumuzaJohnbaptist5/print_hub.git
cd print_hub/backend

# 2. Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create .env file
cp .env.example .env
# Edit .env with your settings

# 5. Run migrations
python manage.py migrate

# 6. Create superuser
python manage.py createsuperuser

# 7. Run development server
python manage.py runserver
