# 代码组织规范

## 核心原则

**模块化 + 简洁实用 + 面向对象**

## 模块化要求

- 每个模块只负责一个明确的功能领域
- 模块之间通过清晰的接口通信
- 避免循环依赖
- 使用依赖注入提高可测试性

## 面向对象要求

- 使用类来组织相关的数据和行为
- 遵循 SOLID 原则：
  - **单一职责原则（SRP）**：一个类只负责一个功能领域
  - **开闭原则（OCP）**：对扩展开放，对修改关闭
  - **里氏替换原则（LSP）**：子类可以替换父类
  - **接口隔离原则（ISP）**：客户端不应依赖它不需要的接口
  - **依赖倒置原则（DIP）**：依赖抽象而不是具体实现
- 合理使用继承和组合
- 使用抽象类和接口定义契约

## 简洁实用要求

- 避免过度设计
- 不要为了设计模式而使用设计模式
- 代码要易读、易维护
- 优先选择简单直接的解决方案
- 只在真正需要时才引入抽象

## 推荐的目录结构

### Python 项目

```
project/
├── src/
│   ├── models/          # 数据模型
│   │   ├── __init__.py
│   │   ├── user.py
│   │   └── product.py
│   ├── services/        # 业务逻辑服务
│   │   ├── __init__.py
│   │   ├── user_service.py
│   │   └── payment_service.py
│   ├── repositories/    # 数据访问层
│   │   ├── __init__.py
│   │   ├── user_repository.py
│   │   └── product_repository.py
│   ├── controllers/     # 控制器（Web 应用）
│   │   ├── __init__.py
│   │   ├── user_controller.py
│   │   └── product_controller.py
│   ├── utils/           # 工具函数
│   │   ├── __init__.py
│   │   ├── validators.py
│   │   └── helpers.py
│   └── config/          # 配置文件
│       ├── __init__.py
│       └── settings.py
├── tests/               # 测试文件（镜像 src 结构）
│   ├── models/
│   │   ├── test_user.py
│   │   └── test_product.py
│   ├── services/
│   │   ├── test_user_service.py
│   │   └── test_payment_service.py
│   └── repositories/
│       ├── test_user_repository.py
│       └── test_product_repository.py
├── docs/                # 文档
├── scripts/             # 脚本工具
├── requirements.txt     # 依赖
└── README.md
```

### JavaScript/TypeScript 项目

```
project/
├── src/
│   ├── models/          # 数据模型
│   │   ├── User.ts
│   │   └── Product.ts
│   ├── services/        # 业务逻辑服务
│   │   ├── UserService.ts
│   │   └── PaymentService.ts
│   ├── repositories/    # 数据访问层
│   │   ├── UserRepository.ts
│   │   └── ProductRepository.ts
│   ├── controllers/     # 控制器（Web 应用）
│   │   ├── UserController.ts
│   │   └── ProductController.ts
│   ├── utils/           # 工具函数
│   │   ├── validators.ts
│   │   └── helpers.ts
│   └── config/          # 配置文件
│       └── settings.ts
├── tests/               # 测试文件
│   ├── models/
│   ├── services/
│   └── repositories/
├── docs/                # 文档
├── scripts/             # 脚本工具
├── package.json
└── README.md
```

### Java 项目

```
project/
├── src/
│   ├── main/
│   │   └── java/
│   │       └── com/
│   │           └── company/
│   │               └── project/
│   │                   ├── model/          # 数据模型
│   │                   │   ├── User.java
│   │                   │   └── Product.java
│   │                   ├── service/        # 业务逻辑服务
│   │                   │   ├── UserService.java
│   │                   │   └── PaymentService.java
│   │                   ├── repository/     # 数据访问层
│   │                   │   ├── UserRepository.java
│   │                   │   └── ProductRepository.java
│   │                   ├── controller/     # 控制器
│   │                   │   ├── UserController.java
│   │                   │   └── ProductController.java
│   │                   ├── util/           # 工具类
│   │                   │   ├── Validators.java
│   │                   │   └── Helpers.java
│   │                   └── config/         # 配置
│   │                       └── AppConfig.java
│   └── test/
│       └── java/
│           └── com/
│               └── company/
│                   └── project/
│                       ├── service/
│                       └── repository/
├── docs/
└── README.md
```

## 分层架构示例

### 三层架构

```
┌─────────────────────────────────┐
│      Controller Layer           │  ← 处理 HTTP 请求/响应
│  (UserController, etc.)         │
└─────────────────────────────────┘
              ↓
┌─────────────────────────────────┐
│      Service Layer               │  ← 业务逻辑
│  (UserService, PaymentService)  │
└─────────────────────────────────┘
              ↓
┌─────────────────────────────────┐
│      Repository Layer            │  ← 数据访问
│  (UserRepository, etc.)         │
└─────────────────────────────────┘
              ↓
┌─────────────────────────────────┐
│         Database                 │
└─────────────────────────────────┘
```

## 依赖注入示例

### Python

```python
# repositories/user_repository.py
class UserRepository:
    """用户数据访问层"""
    def __init__(self, db):
        self.db = db

    def find_by_id(self, user_id):
        return self.db.query("SELECT * FROM users WHERE id = ?", user_id)

# services/user_service.py
class UserService:
    """用户业务逻辑服务"""
    def __init__(self, user_repository, logger):
        # 依赖注入：通过构造函数注入依赖
        self.user_repository = user_repository
        self.logger = logger

    def get_user(self, user_id):
        self.logger.info(f"获取用户信息：{user_id}")
        return self.user_repository.find_by_id(user_id)

# main.py
# 组装依赖
db = Database()
logger = Logger()
user_repository = UserRepository(db)
user_service = UserService(user_repository, logger)
```

### JavaScript/TypeScript

```typescript
// repositories/UserRepository.ts
export class UserRepository {
    constructor(private db: Database) {}

    findById(userId: number): User {
        return this.db.query("SELECT * FROM users WHERE id = ?", userId);
    }
}

// services/UserService.ts
export class UserService {
    constructor(
        private userRepository: UserRepository,
        private logger: Logger
    ) {}

    getUser(userId: number): User {
        this.logger.info(`获取用户信息：${userId}`);
        return this.userRepository.findById(userId);
    }
}

// main.ts
// 组装依赖
const db = new Database();
const logger = new Logger();
const userRepository = new UserRepository(db);
const userService = new UserService(userRepository, logger);
```

## 接口和抽象示例

### Python

```python
from abc import ABC, abstractmethod

# 定义接口（抽象基类）
class IUserRepository(ABC):
    """用户仓储接口"""

    @abstractmethod
    def find_by_id(self, user_id):
        """根据ID查找用户"""
        pass

    @abstractmethod
    def save(self, user):
        """保存用户"""
        pass

# 实现接口
class MySQLUserRepository(IUserRepository):
    """MySQL 用户仓储实现"""

    def __init__(self, db):
        self.db = db

    def find_by_id(self, user_id):
        return self.db.query("SELECT * FROM users WHERE id = ?", user_id)

    def save(self, user):
        self.db.execute("INSERT INTO users ...", user)

# 服务依赖接口而不是具体实现
class UserService:
    def __init__(self, user_repository: IUserRepository):
        self.user_repository = user_repository
```

### TypeScript

```typescript
// 定义接口
interface IUserRepository {
    findById(userId: number): User;
    save(user: User): void;
}

// 实现接口
class MySQLUserRepository implements IUserRepository {
    constructor(private db: Database) {}

    findById(userId: number): User {
        return this.db.query("SELECT * FROM users WHERE id = ?", userId);
    }

    save(user: User): void {
        this.db.execute("INSERT INTO users ...", user);
    }
}

// 服务依赖接口而不是具体实现
class UserService {
    constructor(private userRepository: IUserRepository) {}
}
```

## 避免过度设计的例子

### ❌ 过度设计

```python
# 不必要的抽象层
class AbstractBaseFactory:
    pass

class UserFactory(AbstractBaseFactory):
    pass

class UserBuilder:
    pass

class UserValidator:
    pass

# 只是为了创建一个简单的用户对象
user = UserFactory().create(UserBuilder().with_name("John").build())
```

### ✅ 简洁实用

```python
# 直接创建用户对象
user = User(name="John", email="john@example.com")

# 如果需要验证，直接在模型中实现
class User:
    def __init__(self, name, email):
        self.validate(name, email)
        self.name = name
        self.email = email

    def validate(self, name, email):
        if not name:
            raise ValueError("用户名不能为空")
        if "@" not in email:
            raise ValueError("邮箱格式不正确")
```
