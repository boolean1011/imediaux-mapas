package br.diego.i30launcher.nav.gh;

import com.graphhopper.config.Profile;
import com.graphhopper.json.Statement;
import com.graphhopper.util.CustomModel;
import com.graphhopper.util.TurnCostsConfig;

/** Perfil "car" montado em código (sem Jackson/JSON), idêntico ao car.json embutido no GraphHopper 11.1. */
public final class CarProfile {
    public static CustomModel model() {
        return new CustomModel().setDistanceInfluence(90d)
                .addToPriority(Statement.If("!car_access", Statement.Op.MULTIPLY, "0"))
                .addToSpeed(Statement.If("true", Statement.Op.LIMIT, "car_average_speed"));
    }
    public static Profile profile(boolean turnCosts) {
        Profile p = new Profile("car").setCustomModel(model());
        if (turnCosts) p.setTurnCostsConfig(TurnCostsConfig.car());
        return p;
    }
}
