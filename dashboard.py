import os
from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException, Depends, status
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import mysql.connector
import uuid 
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware
from urllib.parse import quote, unquote

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*']
)

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="picture") 
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# conn = mysql.connector.connect(
#             host="localhost",
#             user="root",
#             password="Om15121969" ,
#             database = "fcia"
#         )
# cursor = conn.cursor()

# إعداد قاعدة البيانات
def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="Om15121969",
            database="fcia"
        )
        return conn
    except mysql.connector.Error as e:
        print(f"Error connecting to database: {e}")
        if e.errno == 1049:
            create_database()
            return get_db_connection()
        raise e


# not used yet  
def create_database():
    """إنشاء قاعدة البيانات والجداول إذا لم تكن موجودة"""
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="Om15121969"
        )
        cursor = conn.cursor()
        
        cursor.execute("CREATE DATABASE IF NOT EXISTS fcai")
        cursor.execute("USE fcai")
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                admin_year INT NOT NULL,
                src VARCHAR(500),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS content (
                id INT AUTO_INCREMENT PRIMARY KEY,
                admin_id INT,
                year INT NOT NULL,
                term INT NOT NULL,
                content_type ENUM('lecture', 'video', 'summarize', 'exam', 'section') NOT NULL,
                subject VARCHAR(255) NOT NULL,
                video_url VARCHAR(500),
                files_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("SELECT COUNT(*) FROM admins")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO admins (email, password, admin_year, src) VALUES
                ('admin@fcai.com', 'admin123', 1, '/static/default-admin.jpg'),
                ('test@fcai.com', 'test123', 2, '/static/default-admin.jpg')
            """)
        
        conn.commit()
        cursor.close()
        conn.close()
        print("Database and tables created successfully")
        
    except mysql.connector.Error as e:
        print(f"Error creating database: {e}")
        raise e


sessions = {}


async def get_current_user(request: Request):
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in sessions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="غير مصرح بالدخول")
    return sessions[session_id]




@app.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    return """
    <html>
        <head>
            <title>زاكر - الصفحة الرئيسية</title>
            <style>
                body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
                a { display: inline-block; margin: 10px; padding: 10px 20px; background: #007bff; color: white; text-decoration: none; border-radius: 5px; }
            </style>
        </head>
        <body>
            <h1>مرحباً بكم في منصة زاكر</h1>
            <p>منصة مساعدة الطلاب على المذاكرة والتحصيل</p>
            <a href="/login">تسجيل الدخول</a>
            <a href="/dashboard">لوحة التحكم (تسجيل الدخول مطلوب)</a>
        </body>
    </html>
    """


@app.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...)
):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT * FROM admins WHERE email = %s AND password = %s", (email, password))
        admin = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if admin:
            session_id = str(uuid.uuid4())
            sessions[session_id] = {
                "admin_id": admin["id"],
                "email": admin["email"],
                "year": admin["admin_year"] ,
                "name": admin["admin_name"] 
            }
            
            response = RedirectResponse(url="/dashboard", status_code=302)
            response.set_cookie(key="session_id", value=session_id)
            return response
        else:
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": "البريد الإلكتروني أو كلمة المرور غير صحيحة"
            })
            
    except Exception as e:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": f"حدث خطأ في النظام: {str(e)}"
        })


@app.get("/dashboard")
async def dashboard_page(request: Request, user: dict = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT * FROM admins WHERE id = %s", (user["admin_id"],))
        admin_info = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "admin_info": {
                "image_url": admin_info.get("src", "/static/default-admin.jpg"),
                "year": admin_info.get("admin_year", "غير محدد") ,
                "name" : admin_info.get("admin_name" , "مشرف - اسم غير محدد")
            }
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في الخادم: {str(e)}")


def changeYear(year):  
    years = ["first" , "second" , "third" , "fourth"]
    return f"{years[year-1]}_year" 

def changeTerm(term):  
    years = ["first" , "second"]
    return f"{years[term-1]}_term" 

def try_get_user(request: Request):
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in sessions:
        return None
    return sessions[session_id]

@app.post("/add-content") 
async def addContent(  
    request : Request ,
    year : str = Form(...) , 
    term : str = Form(...) ,  
    content_type : str = Form(...) ,  
    subject : str = Form(...) ,  
    files : UploadFile = File(...)
) :  
    
    user =   try_get_user(request)
    if not user : 
        raise HTTPException(status_code=302)   
 
    
    name = user["name"] 

    print(name)

    path = Path("uploads") / changeYear( int(year) ) / changeTerm(int(term)) / subject / content_type  ; 
    path.mkdir(parents = True , exist_ok = True) 

    full_path = path / files.filename ;  

    with open(full_path , "wb") as file : 
        file.write(files.file.read())  


    sql = """
        INSERT INTO content (year, term, subject, content_type , files_path , type , size , admin_name)
        VALUES (%s, %s, %s, %s, %s , %s , %s , %s);
        """
    #* important for next db queries 
    safePath = full_path.as_posix() 
    suffix = full_path.suffix 
    size = files.size 
    print(size)
    values = (
        changeYear(int(year)),
        changeTerm(int(term)),
        subject,
        content_type,
        str(safePath) , 
        suffix , 
        size , 
        name
    )

    conn = get_db_connection() 
    cursor = conn.cursor()

    cursor.execute(sql , values) 
    conn.commit()  
    cursor.close()
    return {"message" : "تم الرفع بنجاح"}        


@app.post("/get-content") 
def getContent(
    delete_year : str = Form(...) , 
    delete_term : str = Form(...) , 
    delete_subject : str = Form(...) , 
    delete_content_type : str = Form(...) ,
) : 
    path = Path("uploads")/changeYear(int(delete_year))/changeTerm(int(delete_term))/delete_subject/delete_content_type 

    if not path.exists(): 
        raise HTTPException(status_code=400 , detail="no data") 
    
    list = []
    for file in path.iterdir() : 
        list.append({"file" : file.name , "path" : path / file.name})

    if len(list) == 0 : 
         raise HTTPException(status_code=400 , detail="no data") 
    
    return list
         

@app.post("/delete_content")
async def delete_content(request: Request): 
    # data = await request.json()
    #   file_path = data.get("file_path")

    #   safe_path = file_path.replace("/", "\\")
    #   print(safe_path)
    #   if os.path.exists(safe_path):
    #   os.remove(safe_path)
    #   return {"detail": f"{file_path} deleted successfully"}
    # else:
    #     return {"detail": "file not found"}
    data = await request.json() 

    path = Path(data.get("file_path")) 
    print(path)
    if path.exists() : 
        path.unlink()   
        conn = get_db_connection() 
        cursor = conn.cursor() 
        cursor.execute("delete from content where files_path = %s "  ,( path.as_posix() , )) 
        conn.commit()
        return {"message" :  f"deleting {path.name} was success"}
    else : 
        raise HTTPException(status_code=400 , detail="الملف غير موجود")

@app.get("/display-content") 
def displayContent(subject : str , year : str , term : str , wanted : str ) : 
    path = Path("uploads") / changeYear(int(year)) / changeTerm(int(term)) / subject.lower() / wanted.lower()   

    print(path)
    if  path.exists() :  
        files = [] 
        counter = 1  
        conn = get_db_connection() 
        cursor = conn.cursor()
        for file in path.iterdir() : 
            cursor.execute("SELECT downloads , type , size , admin_name  from content WHERE files_path = %s" , ( file.as_posix() ,)  ) 
            result = cursor.fetchone()
            files.append({f"file" : file.name , "file_path" : path , "file_downloads" : result[0] if result[0] else 0  , "file_type" : result[1] , "file_size" : round(result[2] / (1024 * 1024) ,2)  , "admin_name" : result[3] }) 
        return files
    
    elif not path.exists() or len(files) == 0: 
        raise HTTPException(status_code=400 , detail="لا يوجد محتوى للعرض")      


@app.get("/download")
def download(file_path: str): 
    # decode the parameter value
    decoded = unquote(file_path) # => uploads/year/term/subject
    # creating the path with the decoded path
    path = Path(decoded) 
    # if the file exists
    if path.exists(): 
        # extracting the name from the path
        filename = path.name 
        encoded_name = quote(filename)
        headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}"}
        return FileResponse(path, headers=headers)
    return {"error": "File not found"} 


@app.get("/stats/views") 
def views(path : str):   
    conn = get_db_connection() 
    cursor = conn.cursor()
    normalized_path = path.replace('\\', '/') 
    print(normalized_path)
    cursor.execute("UPDATE content SET views = views + 1  WHERE files_path = %s" , ( normalized_path, ))  
    conn.commit()
    result = cursor.fetchone() 
    print(result)
    cursor.close()


@app.get("/stats/downloads") 
def downloads(path : str):   
    conn = get_db_connection() 
    cursor = conn.cursor()
    normalized_path = path.replace('\\', '/') 
    print(normalized_path)
    cursor.execute("UPDATE content SET downloads = downloads + 1  WHERE files_path = %s" , ( normalized_path, ))  
    conn.commit()
    result = cursor.fetchone() 
    cursor.close()

    