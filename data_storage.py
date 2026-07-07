"""
化工行业信息爬虫工具 - 数据存储模块
使用SQLite数据库持久化存储抓取的数据
"""

import sqlite3,os
import json
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
from pathlib import Path

import config


@dataclass
class ChemNewsItem:
    """化工新闻数据模型"""
    id: Optional[int] = None
    title: str = ""
    content: str = ""
    source: str = ""  # 来源网站
    source_url: str = ""
    category: str = ""  # 行情价格/行业动态/市场分析/政策法规
    publish_date: Optional[datetime] = None
    created_at: Optional[datetime] = None
    keywords: str = ""  # 相关化工产品关键词
    summary: str = ""  # 摘要
    is_sent: bool = False  # 是否已发送邮件

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content[:500] + '...' if len(self.content) > 500 else self.content,
            'source': self.source,
            'source_url': self.source_url,
            'category': self.category,
            'publish_date': self.publish_date.isoformat() if self.publish_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'keywords': self.keywords,
            'summary': self.summary,
            'is_sent': self.is_sent,
        }


class ChemDatabase:
    """化工信息数据库管理类"""
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or config.DATABASE_PATH
        self._ensure_directory()
        self._init_database()
    
    def _ensure_directory(self):
        """确保数据库目录存在"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        try:
            conn = sqlite3.connect(self.db_path, timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
        except (sqlite3.OperationalError, PermissionError) as e:
            fb = os.path.join(os.environ.get("TEMP","/tmp"),"chem_info_fallback.db")
            print(f"[WARN] DB fallback: {fb}")
            conn = sqlite3.connect(fb, timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_database(self):
        """初始化数据库表结构"""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chem_news (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT,
                    source TEXT,
                    source_url TEXT,
                    category TEXT,
                    publish_date TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    keywords TEXT,
                    summary TEXT,
                    is_sent BOOLEAN DEFAULT 0
                )
            """)
            
            # 创建索引
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_news_date 
                ON chem_news(publish_date DESC)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_news_category 
                ON chem_news(category)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_news_source 
                ON chem_news(source)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_news_sent 
                ON chem_news(is_sent)
            """)
            
            # 创建爬虫日志表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS spider_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    spider_name TEXT,
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    items_count INTEGER,
                    status TEXT,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 创建邮件发送记录表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS email_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    send_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    recipient TEXT,
                    subject TEXT,
                    items_count INTEGER,
                    status TEXT,
                    error_message TEXT
                )
            """)

            # A股行情快照（阶段一新增，带溯源字段；阶段二加 llm_* 结论字段）
            conn.execute("""
                CREATE TABLE IF NOT EXISTS stock_market_snapshot (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_date TEXT,
                    source TEXT,
                    fetched_at TIMESTAMP,
                    data_complete BOOLEAN DEFAULT 1,
                    indices TEXT,
                    breadth TEXT,
                    north_flow TEXT,
                    sectors TEXT,
                    indicators TEXT,
                    news TEXT,
                    llm_decision TEXT,
                    llm_score INTEGER,
                    llm_confidence REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 阶段二迁移：为旧快照表补加 LLM 结论列（幂等，列已存在则跳过）
            for _col, _ctype in (("llm_decision", "TEXT"), ("llm_score", "INTEGER"), ("llm_confidence", "REAL")):
                try:
                    conn.execute("ALTER TABLE stock_market_snapshot ADD COLUMN %s %s" % (_col, _ctype))
                except sqlite3.OperationalError:
                    pass  # 列已存在

            conn.commit()
    
    def save_news(self, item: ChemNewsItem) -> int:
        """
        保存新闻条目，如果已存在相同URL则更新
        返回: 记录ID
        """
        with self._get_connection() as conn:
            # 检查是否已存在
            existing = conn.execute(
                "SELECT id FROM chem_news WHERE source_url = ?",
                (item.source_url,)
            ).fetchone()
            
            if existing:
                # 更新已有记录
                conn.execute("""
                    UPDATE chem_news 
                    SET title = ?, content = ?, category = ?, 
                        keywords = ?, summary = ?, publish_date = ?
                    WHERE id = ?
                """, (
                    item.title, item.content, item.category,
                    item.keywords, item.summary, item.publish_date,
                    existing['id']
                ))
                conn.commit()
                return existing['id']
            else:
                # 插入新记录
                cursor = conn.execute("""
                    INSERT INTO chem_news 
                    (title, content, source, source_url, category, 
                     publish_date, keywords, summary, is_sent, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    item.title, item.content, item.source, item.source_url,
                    item.category, item.publish_date, item.keywords, item.summary,
                    item.is_sent, datetime.now()
                ))
                conn.commit()
                return cursor.lastrowid
    
    def get_news_by_date_range(
        self, 
        start_date: datetime, 
        end_date: datetime,
        category: Optional[str] = None,
        limit: int = 100
    ) -> List[ChemNewsItem]:
        """获取指定日期范围的新闻"""
        query = """
            SELECT * FROM chem_news 
            WHERE publish_date BETWEEN ? AND ?
        """
        params = [start_date, end_date]
        
        if category:
            query += " AND category = ?"
            params.append(category)
        
        query += " ORDER BY publish_date DESC LIMIT ?"
        params.append(limit)
        
        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_item(row) for row in rows]
    
    def get_latest_news(
        self, 
        hours: int = 24,
        category: Optional[str] = None,
        limit: int = 50
    ) -> List[ChemNewsItem]:
        """获取最近N小时的新闻"""
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        return self.get_news_by_date_range(start_time, end_time, category, limit)
    
    def get_unsent_news(self, limit: int = 100) -> List[ChemNewsItem]:
        """获取未发送的新闻"""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM chem_news 
                WHERE is_sent = 0
                ORDER BY publish_date DESC
                LIMIT ?
            """, (limit,)).fetchall()
            return [self._row_to_item(row) for row in rows]
    
    def mark_as_sent(self, news_ids: List[int]):
        """标记新闻为已发送"""
        with self._get_connection() as conn:
            for news_id in news_ids:
                conn.execute(
                    "UPDATE chem_news SET is_sent = 1 WHERE id = ?",
                    (news_id,)
                )
            conn.commit()
    
    def get_news_stats(self, days: int = 7) -> Dict[str, Any]:
        """获取新闻统计信息"""
        start_date = datetime.now() - timedelta(days=days)
        
        with self._get_connection() as conn:
            # 总数
            total = conn.execute(
                "SELECT COUNT(*) FROM chem_news WHERE publish_date > ?",
                (start_date,)
            ).fetchone()[0]
            
            # 按分类统计
            category_stats = conn.execute("""
                SELECT category, COUNT(*) as count 
                FROM chem_news 
                WHERE publish_date > ?
                GROUP BY category
            """, (start_date,)).fetchall()
            
            # 按来源统计
            source_stats = conn.execute("""
                SELECT source, COUNT(*) as count 
                FROM chem_news 
                WHERE publish_date > ?
                GROUP BY source
            """, (start_date,)).fetchall()
            
            return {
                'total': total,
                'by_category': {row['category']: row['count'] for row in category_stats},
                'by_source': {row['source']: row['count'] for row in source_stats},
                'days': days,
            }
    
    def search_news(
        self, 
        keyword: str, 
        category: Optional[str] = None,
        limit: int = 50
    ) -> List[ChemNewsItem]:
        """搜索新闻"""
        query = """
            SELECT * FROM chem_news 
            WHERE (title LIKE ? OR content LIKE ? OR keywords LIKE ?)
        """
        params = [f'%{keyword}%', f'%{keyword}%', f'%{keyword}%']
        
        if category:
            query += " AND category = ?"
            params.append(category)
        
        query += " ORDER BY publish_date DESC LIMIT ?"
        params.append(limit)
        
        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_item(row) for row in rows]
    
    def get_news_by_id(self, news_id: int) -> Optional[ChemNewsItem]:
        """通过ID获取单条新闻"""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM chem_news WHERE id = ?",
                (news_id,)
            ).fetchone()
            return self._row_to_item(row) if row else None
    
    def delete_old_news(self, days: int = 30) -> int:
        """删除N天前的旧数据，返回删除数量"""
        cutoff_date = datetime.now() - timedelta(days=days)
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM chem_news WHERE publish_date < ?",
                (cutoff_date,)
            )
            conn.commit()
            return cursor.rowcount
    
    def log_spider_run(
        self, 
        spider_name: str, 
        start_time: datetime,
        end_time: datetime,
        items_count: int,
        status: str,
        error_message: str = ""
    ):
        """记录爬虫运行日志"""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO spider_logs 
                (spider_name, start_time, end_time, items_count, status, error_message)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (spider_name, start_time, end_time, items_count, status, error_message))
            conn.commit()
    
    def log_email_send(
        self, 
        recipient: str,
        subject: str,
        items_count: int,
        status: str,
        error_message: str = ""
    ):
        """记录邮件发送日志"""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO email_logs 
                (recipient, subject, items_count, status, error_message)
                VALUES (?, ?, ?, ?, ?)
            """, (recipient, subject, items_count, status, error_message))
            conn.commit()
    
    def get_spider_logs(self, limit: int = 20) -> List[Dict]:
        """获取爬虫运行日志"""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM spider_logs 
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,)).fetchall()
            return [dict(row) for row in rows]
    
    def get_email_logs(self, limit: int = 20) -> List[Dict]:
        """获取邮件发送日志"""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM email_logs 
                ORDER BY send_time DESC
                LIMIT ?
            """, (limit,)).fetchall()
            return [dict(row) for row in rows]
    
    def _row_to_item(self, row: sqlite3.Row) -> ChemNewsItem:
        """将数据库行转换为ChemNewsItem对象"""
        # 处理日期字段
        def parse_date(date_val):
            if date_val is None:
                return None
            if isinstance(date_val, datetime):
                return date_val
            if isinstance(date_val, str):
                try:
                    return datetime.fromisoformat(date_val.replace('Z', '+00:00'))
                except:
                    return datetime.now()
            return None
        
        return ChemNewsItem(
            id=row['id'],
            title=row['title'],
            content=row['content'],
            source=row['source'],
            source_url=row['source_url'],
            category=row['category'],
            publish_date=parse_date(row['publish_date']),
            created_at=parse_date(row['created_at']),
            keywords=row['keywords'],
            summary=row['summary'],
            is_sent=bool(row['is_sent']),
        )


    def save_market_snapshot(self, analysis: Dict[str, Any], llm_result: Optional[Dict] = None) -> int:
        """保存一次 A股行情快照，含溯源字段(source/fetched_at/data_complete)；
        可选存 LLM 研判结论(llm_decision/llm_score/llm_confidence)。
        返回记录 ID；analysis 为 None 或空时不存储。"""
        if not analysis:
            return 0

        def _j(v):
            try:
                return json.dumps(v, ensure_ascii=False)
            except Exception:
                return "[]"

        lr = llm_result or {}
        llm_decision = lr.get("decision")
        try:
            llm_score = int(lr.get("score", 0))
        except (TypeError, ValueError):
            llm_score = 0
        try:
            llm_confidence = float(lr.get("confidence", 0))
        except (TypeError, ValueError):
            llm_confidence = 0.0

        with self._get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO stock_market_snapshot
                (trade_date, source, fetched_at, data_complete,
                 indices, breadth, north_flow, sectors, indicators, news,
                 llm_decision, llm_score, llm_confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                analysis.get("date"),
                analysis.get("source"),
                analysis.get("fetched_at"),
                int(bool(analysis.get("data_complete"))),
                _j(analysis.get("indices")),
                _j(analysis.get("breadth")),
                _j(analysis.get("north_flow")),
                _j(analysis.get("sectors")),
                _j(analysis.get("indicators")),
                _j(analysis.get("news")),
                llm_decision,
                llm_score,
                llm_confidence,
            ))
            conn.commit()
            return cursor.lastrowid

# 单例模式
db = ChemDatabase()


if __name__ == "__main__":
    # 测试数据库功能
    print("测试数据库连接...")
    
    # 创建测试数据
    test_item = ChemNewsItem(
        title="测试化工新闻",
        content="这是测试内容...",
        source="测试源",
        source_url="https://test.com/1",
        category="行情价格",
        keywords="甲醇,乙醇",
        summary="测试摘要",
    )
    
    news_id = db.save_news(test_item)
    print(f"保存新闻成功，ID: {news_id}")
    
    # 查询
    stats = db.get_news_stats(days=1)
    print(f"统计信息: {stats}")
    
    print("数据库测试完成！")
