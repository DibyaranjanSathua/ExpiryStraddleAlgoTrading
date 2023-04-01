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
6. sudo nano /etc/nginx/sites-available/algotrading-dashboard
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
7. sudo ln -s /etc/nginx/sites-available/algotrading-dashboard /etc/nginx/sites-enabled 
8. sudo nginx -t
9. sudo systemctl restart nginx
10. Edit /etc/nginx/nginx.conf change user to ubuntu. Else you will see permission issue while connecting to the socket.

## Crontab
```shell
14 4 * * 1-5 cd /home/ubuntu/ExpiryStraddleAlgoTrading; python3 main.py --clean-up
15 4 * * 1-5 cd /home/ubuntu/ExpiryStraddleAlgoTrading; python3 main.py --market-feeds --option-type CE
15 4 * * 1-5 cd /home/ubuntu/ExpiryStraddleAlgoTrading; python3 main.py --market-feeds --option-type PE
18 4 * * 1-5 cd /home/ubuntu/ExpiryStraddleAlgoTrading; python3 main.py --trading
# Kill if the process is still running once the process is exited
30 10 * * * pkill -f main.py
```

