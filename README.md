# ExpiryStraddleAlgoTrading
Expiry day Straddle Algo Trading


## Alembic migration
alembic upgrade head

## Installing Gunicorn and running app
Install using apt or pip3
sudo apt install gunicorn
pip3 install gunicorn

gunicorn --bind 0.0.0.0:8080 wsgi:app


## Install nginx
https://www.digitalocean.com/community/tutorials/how-to-install-nginx-on-ubuntu-20-04
1. sudo apt install nginx
2. sudo systemctl status nginx
3. sudo systemctl stop nginx
4. sudo systemctl start nginx
5. sudo systemctl restart nginx
6. sudo nginx -t

## Install PostgesSQL
https://www.digitalocean.com/community/tutorials/how-to-install-postgresql-on-ubuntu-22-04-quickstart
1. sudo -u postgres psql
2. CREATE DATABASE algotrading;
3. CREATE USER algobot WITH PASSWORD 'algobot123';
4. GRANT ALL PRIVILEGES ON DATABASE algotrading TO algobot;
5. alembic upgrade head


## Initialize the db table
1. export PYTHONPATH=/home/ubuntu/ExpiryStraddleAlgoTrading
2. python3 dashboard/db/db_init_table.py


## Deploying dash app to AWS EC2 (Ubuntu instance)
1. sudo nano /etc/systemd/system/gunicorn.service
2. Add the following contents
   ```text
    [Unit]
    Description=Gunicorn instance to serve myproject
    After=network.target
    
    [Service]
    User=ubuntu
    Group=ubuntu
    WorkingDirectory=/home/ubuntu/ExpiryStraddleAlgoTrading
    #Environment="PATH=/home/sammy/myproject/myprojectenv/bin"
    ExecStart=/usr/bin/gunicorn --workers 2 --bind unix:gunicorn.sock -m 007 wsgi:app
    
    [Install]
    WantedBy=multi-user.target
    ```
3. sudo systemctl start gunicorn
4. sudo systemctl enable gunicorn
5. sudo systemctl status gunicorn
6. Test the socket activation mechanism, curl --unix-socket /home/ubuntu/ExpiryStraddleAlgoTrading/gunicorn.sock localhost
7. sudo nano /etc/nginx/sites-available/algotrading-dashboard
    ```text
    server {
        listen 80;
        server_name your_domain www.your_domain;
    
        location / {
            include proxy_params;
            proxy_pass http://unix:/home/ubuntu/ExpiryStraddleAlgoTrading/gunicorn.sock;
        }
    }
    ```
8. sudo ln -s /etc/nginx/sites-available/algotrading-dashboard /etc/nginx/sites-enabled 
9. sudo nginx -t
10. sudo systemctl restart nginx
11. Edit /etc/nginx/nginx.conf change user to ubuntu. Else you will see permission issue while connecting to the socket.


## Install Redis
https://redis.io/docs/install/install-redis/install-redis-on-linux/
1. sudo apt install lsb-release curl gpg
2. curl -fsSL https://packages.redis.io/gpg | sudo gpg --dearmor -o /usr/share/keyrings/redis-archive-keyring.gpg 
3. echo "deb [signed-by=/usr/share/keyrings/redis-archive-keyring.gpg] https://packages.redis.io/deb $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/redis.list 
4. sudo apt update 
5. sudo apt install redis


## How to reference user database in postgres
https://stackoverflow.com/questions/22256124/cannot-create-a-database-table-named-user-in-postgresql
1. INSERT INTO "user" (username, password, role) VALUES ('NIHKA1018', 'password', 'Admin');
2. select * from "user";


## Crontab
```shell
14 4 * * 1-5 cd /home/ubuntu/ExpiryStraddleAlgoTrading; python3 main.py --clean-up
15 4 * * 1-5 cd /home/ubuntu/ExpiryStraddleAlgoTrading; python3 main.py --market-feeds --option-type CE
15 4 * * 1-5 cd /home/ubuntu/ExpiryStraddleAlgoTrading; python3 main.py --market-feeds --option-type PE
18 4 * * 1-5 cd /home/ubuntu/ExpiryStraddleAlgoTrading; python3 main.py --trading
# Kill if the process is still running once the process is exited
30 10 * * * pkill -f main.py
```

