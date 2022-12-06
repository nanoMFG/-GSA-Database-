from sqlalchemy import Column, String, Integer, ForeignKey, Date, Boolean, Float
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import select, func, text, and_
from sqlalchemy.sql import exists
from sqlalchemy.schema import Table

from grdb.database import Base, class_registry


class Recipe(Base):
    __tablename__ = 'recipe'
    # Basic integer primary key
    id = Column(Integer, primary_key=True, info={"verbose_name": "ID"})

    # ONE-TO-MANY: recipe -> preparation_step
    preparation_steps = relationship(
        "PreparationStep",
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="recipe",
    )

    # ONE-TO-MANY: recipe -> experiment
    experiments = relationship(
        "Experiment",
        back_populates="recipe",
    )

    carbon_source = Column(
        String(16),
        info={
            "verbose_name": "Carbon Source",
            "choices": ["CH4", "C2H4", "C2H2", "C6H6"],
            "required": True,
        },
    )
    base_pressure = Column(
        Float,
        info={
            "verbose_name": "Base Pressure",
            "std_unit": "Torr",
            "conversions": {
                "Torr": 1,
                "Pa": 1 / 133.322,
                "mbar": 1 / 1.33322,
                "mTorr": 1.0e-3,
            },
            "required": True,
            "tooltip": "Pressure inside the tube before starting the flow of gases",
        },
    )

    @hybrid_property
    def maximum_temperature(self):
        return max(
            [
                p.furnace_temperature
                for p in self.preparation_steps
                if p.furnace_temperature != None
            ], default = None
        )

    @maximum_temperature.expression
    def maximum_temperature(cls):
        PreparationStep = class_registry["PreparationStep"]
        return (
            select([func.max(PreparationStep.furnace_temperature)])
                .where(PreparationStep.recipe_id == cls.id)
                .correlate(cls)
                .label("maximum_temperature")
        )

    @hybrid_property
    def maximum_pressure(self):
        return max(
            [
                p.furnace_pressure
                for p in self.preparation_steps
                if p.furnace_pressure != None
            ], default = None
        )

    @maximum_pressure.expression
    def maximum_pressure(cls):
        PreparationStep = class_registry["PreparationStep"]
        return (
            select([func.max(PreparationStep.furnace_pressure)])
                .where(PreparationStep.recipe_id == cls.id)
                .correlate(cls)
                .label("maximum_pressure")
        )

    @hybrid_property
    def average_carbon_flow_rate(self):
        steps = [
            p.carbon_source_flow_rate
            for p in self.preparation_steps
            if p.carbon_source_flow_rate != None
        ]
        return sum(steps) / len(steps) 

    @average_carbon_flow_rate.expression
    def average_carbon_flow_rate(cls):
        PreparationStep = class_registry["PreparationStep"]
        return (
            select([func.avg(PreparationStep.carbon_source_flow_rate)])
                .where(PreparationStep.recipe_id == cls.id)
                .correlate(cls)
                .label("average_carbon_flow_rate")
        )

    @hybrid_property
    def max_flow_rate(self):
        steps = [
            (p.hydrogen_flow_rate or 0)+(p.helium_flow_rate or 0)+(p.argon_flow_rate or 0)
            for p in self.preparation_steps
        ]
        return max(steps, default = None)

    @max_flow_rate.expression
    def max_flow_rate(cls):
        PreparationStep = class_registry["PreparationStep"]
        return (
            select([func.max((PreparationStep.hydrogen_flow_rate or 0)+(PreparationStep.helium_flow_rate or 0)+(PreparationStep.argon_flow_rate or 0))])
                .where(PreparationStep.recipe_id == cls.id)
                .correlate(cls)
                .label("max_flow_rate")
        )
    
    @hybrid_property
    def growth_duration(self):
        steps = [
            p.duration
            for p in self.preparation_steps
                if p.name == "Growing" and p.duration!=None
        ]
        return max(steps, default = None)

    @growth_duration.expression
    def growth_duration(cls):
        PreparationStep = class_registry["PreparationStep"]
        return (
            select([func.max(PreparationStep.duration)])
                .where(PreparationStep.recipe_id == cls.id and PreparationStep.name == "Growing")
                .correlate(cls)
                .label("growth_duration")
        )
    
    @hybrid_property
    def carbon_source_flow_rate(self):
        steps = [
            p.carbon_source_flow_rate
            for p in self.preparation_steps
            if p.name == "Growing" and p.carbon_source_flow_rate != None
        ]
        return max(steps, default = None)

    @carbon_source_flow_rate.expression
    def carbon_source_flow_rate(cls):
        PreparationStep = class_registry["PreparationStep"]
        return (
            select([func.avg(PreparationStep.carbon_source_flow_rate)])
                .where(PreparationStep.recipe_id == cls.id and PreparationStep.name == "Growing")
                .correlate(cls)
                .label("carbon_source_flow_rate")
        )

    # NOTE: This is really the carbon source from the first step.
    # Should there be a contraint that the carbon source is the same for all steps??
    # @hybrid_property
    # def carbon_source(self):
    #     vals = [
    #         p.carbon_source
    #         for p in self.preparation_steps
    #         if p.carbon_source is not None
    #     ]
    #     return vals[0]

    # @carbon_source.expression
    # def carbon_source(cls):
    #     PreparationStep = class_registry["PreparationStep"]
    #     return (
    #         select([PreparationStep.carbon_source])
    #         .where(
    #             and_(
    #                 PreparationStep.recipe_id == cls.id,
    #                 PreparationStep.carbon_source != None,
    #             )
    #         )
    #         .correlate(cls)
    #         .limit(1)
    #         .label("carbon_source")
    #     )

    @hybrid_property
    def uses_helium(self):
        return any([p.helium_flow_rate for p in self.preparation_steps])

    @uses_helium.expression
    def uses_helium(cls):
        PreparationStep = class_registry["PreparationStep"]
        s = (
            select([PreparationStep.helium_flow_rate])
                .where(
                and_(
                    PreparationStep.helium_flow_rate != None,
                    PreparationStep.recipe_id == cls.id,
                )
            )
                .correlate(cls)
        )
        return exists(s)

    @hybrid_property
    def uses_argon(self):
        return any([p.argon_flow_rate for p in self.preparation_steps])

    @uses_argon.expression
    def uses_argon(cls):
        PreparationStep = class_registry["PreparationStep"]
        s = (
            select([PreparationStep.argon_flow_rate])
                .where(
                and_(
                    PreparationStep.argon_flow_rate != None,
                    PreparationStep.recipe_id == cls.id,
                )
            )
                .correlate(cls)
        )
        return exists(s)

    @hybrid_property
    def uses_hydrogen(self):
        return any([p.hydrogen_flow_rate for p in self.preparation_steps])

    @uses_hydrogen.expression
    def uses_hydrogen(cls):
        PreparationStep = class_registry["PreparationStep"]
        s = (
            select([PreparationStep.hydrogen_flow_rate])
                .where(
                and_(
                    PreparationStep.hydrogen_flow_rate != None,
                    PreparationStep.recipe_id == cls.id,
                )
            )
                .correlate(cls)
        )
        return exists(s)

    def json_encodable(self):
        # check if necessary
        params = [
            "carbon_source",
            "base_pressure",
            "maximum_temperature",
            "maximum_pressure",
            "max_flow_rate",
            "growth_duration",
            "carbon_source_flow_rate",
            "uses_helium",
            "uses_argon"
        ] 
        json_dict = {'id': self.id}
        for p in params:
            info = getattr(Recipe, p).info
            json_dict[p] = {
                "value": getattr(self, p),
                "unit": info["std_unit"] if "std_unit" in info else None,
            }
        json_dict['preparation_steps'] = None
        if self.preparation_steps:
            json_dict['preparation_steps'] = [p.json_encodable()
                                              for p in self.preparation_steps]
        return json_dict
