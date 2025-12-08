{
  "builds": [
    {
      "src": "sistema_contable/wsgi.py",
      "use": "@vercel/python",
      "config": { "maxLambdaSize": "15mb", "runtime": "python3.9" }
    }
  ],
  "routes": [
    { "src": "/(.*)", "dest": "sistema_contable/wsgi.py" }
  ]
}