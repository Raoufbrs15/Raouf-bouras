from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import logging
import os

# Configuration du logging
logger = logging.getLogger(__name__)

# Base pour les modèles SQLAlchemy
Base = declarative_base()

# Configuration de la base de données SQLite
DATABASE_URL = "sqlite:///./chatbot_prevente.db"

# Créer le moteur de base de données
engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False},  # Nécessaire pour SQLite
    echo=False  # Mettre True pour voir les requêtes SQL dans les logs
)

# Créer une session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Modèle de la table Conversation
class Conversation(Base):
    """
    Modèle représentant une conversation entre l'utilisateur et le chatbot
    """
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    question = Column(String(500), nullable=False, index=True)
    reponse = Column(String(2000), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    def __repr__(self):
        """Représentation string de l'objet pour le debugging"""
        return f"<Conversation(id={self.id}, question='{self.question[:50]}...', timestamp={self.timestamp})>"
    
    def to_dict(self):
        """Convertit l'objet en dictionnaire pour la sérialisation JSON"""
        return {
            "id": self.id,
            "question": self.question,
            "reponse": self.reponse,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }

def init_db():
    """
    Initialise la base de données en créant toutes les tables
    """
    try:
        # Créer toutes les tables définies dans Base.metadata
        Base.metadata.create_all(bind=engine)
        logger.info("Base de données initialisée avec succès")
        
        # Vérifier que la table existe en comptant les enregistrements
        with SessionLocal() as session:
            count = session.query(Conversation).count()
            logger.info(f"Table 'conversations' contient {count} enregistrements")
            
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation de la base de données: {e}")
        raise

def get_db():
    """
    Générateur de session de base de données
    Utilisé comme dépendance dans FastAPI avec Depends()
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Erreur de session de base de données: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def get_db_info():
    """
    Retourne des informations sur la base de données
    Utile pour le debugging et le monitoring
    """
    try:
        with SessionLocal() as session:
            # Compter le nombre total de conversations
            total_conversations = session.query(Conversation).count()
            
            # Obtenir la dernière conversation
            last_conversation = session.query(Conversation).order_by(
                Conversation.timestamp.desc()
            ).first()
            
            # Calculer la taille du fichier de base de données
            db_file_path = DATABASE_URL.replace("sqlite:///./", "")
            db_size = os.path.getsize(db_file_path) if os.path.exists(db_file_path) else 0
            
            return {
                "database_url": DATABASE_URL,
                "total_conversations": total_conversations,
                "last_conversation_time": last_conversation.timestamp.isoformat() if last_conversation else None,
                "database_size_bytes": db_size,
                "database_size_kb": round(db_size / 1024, 2)
            }
            
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des infos DB: {e}")
        return {"error": str(e)}

def reset_database():
    """
    Remet à zéro la base de données en supprimant toutes les données
    ATTENTION: Cette fonction supprime toutes les conversations !
    """
    try:
        with SessionLocal() as session:
            # Compter avant suppression
            count_before = session.query(Conversation).count()
            
            # Supprimer toutes les conversations
            session.query(Conversation).delete()
            session.commit()
            
            logger.info(f"Base de données réinitialisée: {count_before} conversations supprimées")
            return count_before
            
    except Exception as e:
        logger.error(f"Erreur lors de la réinitialisation de la base de données: {e}")
        raise

def backup_database(backup_path: str = None):
    """
    Crée une sauvegarde de la base de données
    """
    import shutil
    
    try:
        db_file_path = DATABASE_URL.replace("sqlite:///./", "")
        
        if not backup_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"backup_chatbot_{timestamp}.db"
        
        if os.path.exists(db_file_path):
            shutil.copy2(db_file_path, backup_path)
            logger.info(f"Sauvegarde créée: {backup_path}")
            return backup_path
        else:
            logger.warning("Fichier de base de données non trouvé pour la sauvegarde")
            return None
            
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde: {e}")
        raise

# Test de connexion (optionnel)
if __name__ == "__main__":
    """
    Script de test pour vérifier la configuration de la base de données
    """
    logging.basicConfig(level=logging.INFO)
    
    try:
        print("🔧 Test de configuration de la base de données...")
        
        # Initialiser la base
        init_db()
        print("✅ Base de données initialisée")
        
        # Tester une session
        with SessionLocal() as session:
            count = session.query(Conversation).count()
            print(f"✅ Connexion réussie - {count} conversations en base")
        
        # Afficher les infos
        info = get_db_info()
        print("📊 Informations de la base:")
        for key, value in info.items():
            print(f"   {key}: {value}")
        
        print("🎉 Configuration de la base de données OK !")
        
    except Exception as e:
        print(f"❌ Erreur de configuration: {e}")
        raise