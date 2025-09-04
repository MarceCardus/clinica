from sqlalchemy import Column, Integer, Date, String, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base

class Procedimiento(Base):
    __tablename__ = 'procedimiento'

    id = Column(Integer, primary_key=True, autoincrement=True)
    idpaciente = Column(Integer, ForeignKey('paciente.idpaciente'), nullable=False)
    fecha = Column(Date, nullable=False)

    iditem = Column(Integer, ForeignKey('item.iditem'), nullable=False)

    comentario = Column(String(200))

    # Relaciones
    paciente = relationship("Paciente", back_populates="procedimientos")
    item = relationship("Item", back_populates="procedimientos")

    # 🔹 AJUSTE: indicar foreign_keys explícitamente y respetar ondelete
    indicaciones = relationship(
        'Indicacion',
        back_populates='procedimiento',
        foreign_keys='Indicacion.idprocedimiento',
        passive_deletes=True,
    )

    def __repr__(self):
        return f"<Procedimiento id={self.id} fecha={self.fecha} iditem={self.iditem}>"
