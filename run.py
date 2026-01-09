import os
from app import create_app

app = create_app()

if __name__ == '__main__':
    # Ortam değişkeninden ayarı çek, yoksa varsayılan olarak KAPALI (False) yap.
    # Sadece 'true', '1' veya 't' gelirse açar.
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() in ['true', '1', 't']
    
    # Geliştirme ortamındaysan True olur, değilse False kalır.
    app.run(debug=debug_mode)