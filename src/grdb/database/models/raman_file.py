from sqlalchemy import Column, String, Integer, ForeignKey, Float, Boolean
from sqlalchemy.orm import relationship, backref
from sqlalchemy.ext.hybrid import hybrid_property

from grdb.database import Base

from urllib.request import urlopen
import ssl
import certifi
from grdb.server.app import s3

class RamanFile(Base):
    """[summary]
    
    Args:
        Base ([type]): [description]
    
    Returns:
        [type]: [description]
    """
    __tablename__ = 'raman_file'
    # Integer primary key
    id = Column(Integer, primary_key=True, info={"verbose_name": "ID"})

    # Foreign key for relationship to Experiment.
    experiment_id = Column(Integer, ForeignKey("experiment.id", ondelete="CASCADE"), index=True)

    # Filename for this raman file - should we add file type?
    filename = Column(String(64))

    # url endpoint for retriving file - should rename to "box_url"?
    url = Column(String(256))

    s3_object_name = Column(String(256))

    #
    wavelength = Column(
        Float,
        info={
            "verbose_name": "Wavelength",
            "std_unit": "nm",
            "conversions": {"nm": 1},
            "required": True,
        },
    )

    # MANY->ONE: raman_files->experiment
    experiment = relationship("Experiment", foreign_keys=experiment_id, back_populates="raman_files")

    # ONE->MANY: raman_file->raman_analysis
    raman_analyses = relationship(
        "RamanAnalysis",
        #uselist=False,
        cascade="all, delete-orphan",
        # foreign_keys="RamanAnalysis.raman_file_id",
        passive_deletes=True,
        back_populates="raman_file",
    )


    def __repr__(self):
        return self._repr(
            id=self.id, experiment_id=self.experiment_id, raman_analyses=self.raman_analyses
        )

    def json_encodable(self):
        params = ["wavelength"]
        json_dict = {}
        json_dict["filename"] = self.filename
        for p in params:
            info = getattr(RamanFile, p).info
            json_dict[p] = {
                "value": getattr(self, p),
                "unit": info["std_unit"] if "std_unit" in info else None,
            }
        return json_dict

    def read_file(self):
        """
        Fetch the raman file from the url and returns the file in json encodable form
        """
        if(self.url is None):
            self.url = s3.create_presigned_url(self.s3_object_name)
            print(self.url,flush=True)
        context = ssl.create_default_context(cafile=certifi.where())
        file = urlopen(self.url,context=context)
        data = []
        for line in file:
            line = line.decode('utf-8').split()
            line = list(map(float, line))
            data.append({'x': line[0], 'y': line[1]})
        return {'data': data}
