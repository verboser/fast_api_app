from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String
from datetime import datetime, timedelta

# Создаём базу и колонки для бд
class Base(DeclarativeBase):
    pass


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(150))
    descr: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(50))
    date: Mapped[datetime] = mapped_column(default=datetime.now)
    priority: Mapped[int] = mapped_column()
    owner_id: Mapped[int] = mapped_column()


#%%
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy import create_engine
import os


# engine = create_engine(
#     "sqlite:///./tasks.db",
#     connect_args={"check_same_thread": False}
# )


# Создаём движок и жизненный цикл для бд
# Получаем URL из переменной окружения, если ее нет — используем SQLite как запасной вариант для локальных тестов
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tasks.db")

# Для MySQL check_same_thread не нужен
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Data init...")

    Base.metadata.create_all(bind=engine)

    yield

    print("Server stopped")


app = FastAPI(lifespan=lifespan)

#%%
from sqlalchemy.orm import sessionmaker

# Получаем базу данных
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
#%%
from pydantic import BaseModel

# Создаём задачу и определяем как будем возвращать её пользователю
class TaskCreate(BaseModel):
    title: str
    descr: str | None
    status: str
    priority: int


class TaskOut(TaskCreate):
    id: int
    date: datetime
    owner_id: int
#%%
from pwdlib import PasswordHash
from fastapi import Depends
from fastapi import HTTPException
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from fastapi.security import OAuth2PasswordRequestForm


SECRET_KEY = "This is a very secret key that supposed to be in secret. Never tell anyone I did that!!!"
ALGO = "HS256"

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    login: Mapped[str] = mapped_column(String(25), unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255))


# Это всё делаем для того, чтобы не дат паролю просочиться в ответ сервера
class UserBase(BaseModel):
    login: str


class UserCreate(UserBase):
    password: str


class UserOut(UserBase):
    id: int


# Делаем релаьное хеширование, потому что это прикольно :)
password_hash = PasswordHash.recommended()

def get_hashed_pwd(password: str) -> str:
    return password_hash.hash(password)


def create_jwt(data: dict):
    encode = data.copy()

    expire = datetime.now() + timedelta(minutes=30)
    encode.update({"exp": expire})
    encoded_jwt = jwt.encode(encode, SECRET_KEY, algorithm=ALGO)
    return encoded_jwt


@app.post("/register/", response_model=UserOut)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = User(login=user.login, hashed_password=get_hashed_pwd(user.password))

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return db_user


@app.post("/login/", response_model=dict)
def login_user(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.login == form_data.username).first()

    if db_user is None or password_hash.verify(form_data.password, db_user.hashed_password) is False:
        raise HTTPException(status_code=401, detail="Wrong login or password")

    access_token = create_jwt(data={"sub": str(db_user.id)})
    return {"access_token": access_token, "token_type": "bearer"}


# Указывает FastAPI, где искать токен (в заголовке Authorization: Bearer <token>)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        # Расшифровываем токен
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGO])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user

#%%
from sqlalchemy import or_

# Пишем эндпоинты

@app.post("/tasks/", response_model=TaskOut)
def create_task(task: TaskCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_task = Task(title=task.title, descr=task.descr, status=task.status, priority=task.priority, owner_id=current_user.id)

    db.add(db_task)
    db.commit()
    db.refresh(db_task)

    return db_task


@app.get("/tasks/", response_model=list[TaskOut])
def get_all_tasks(sort_by: str | None = None,
                  limit: int | None = None,
                  search: str | None = None,
                  db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    query = db.query(Task).filter(Task.owner_id == current_user.id)
    if search is not None:
        query = query.filter(or_(Task.title.contains(search), Task.descr.contains(search)))

    # В реальности, скорее всего полбзователь будет делать сортировку через dropdown menu, так что это чисто заглушка
    if sort_by == "title":
        query = query.order_by(Task.title)
    elif sort_by == "status":
        query = query.order_by(Task.status)
    elif sort_by == "date":
        query = query.order_by(Task.date)
    elif sort_by == "priority":
        query = query.order_by(Task.priority.desc())

    if limit is not None:
        query = query.limit(limit)

    return query.all()


@app.get("/tasks/{task_id}", response_model=TaskOut)
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    return task


@app.put("/tasks/{task_id}", response_model=TaskOut)
def update_task(task_id: int, task: TaskCreate, db: Session = Depends(get_db)):
    upd_task = db.query(Task).filter(Task.id == task_id).first()
    if upd_task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    upd_task.title = task.title
    upd_task.descr = task.descr
    upd_task.status = task.status
    upd_task.priority = task.priority

    db.commit()
    db.refresh(upd_task)

    return upd_task


@app.delete("/tasks/{task_id}", response_model=dict)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    d_task = db.query(Task).filter(Task.id == task_id).first()
    if d_task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    db.delete(d_task)
    db.commit()
    return {"details": "Task deleted"} # Заглушка, чтобы не было пустоты при успешном удалении (как в Линуксе :)