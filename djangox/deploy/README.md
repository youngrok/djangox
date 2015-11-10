## Prerequisite
Install fabric (fabric runs on python 2)
    
    pip install -r requirements
    
customize config

    cp deployconfig_sample.py deployconfig.py
    vi deployconfig.py
 
## Deploy
Prepare database server

	fab setup_db

Prepare web server

	fab setup_web	
		
Deploy

	fab deploy
