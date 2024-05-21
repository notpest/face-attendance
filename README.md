Postgres Schema:

![face_attendance](https://github.com/notpest/face-attendance/assets/113047106/45932506-3ee8-4f7e-a5f4-006c465f9eee)

Trigger Function Code: (make sure to execute the trigger for all required tables)

BEGIN
   IF row(NEW.*) IS DISTINCT FROM row(OLD.*) THEN
      NEW.updated_date = CURRENT_TIMESTAMP;
	  NEW.created_date = OLD.created_date;
	  NEW.created_by = OLD.created_by;
      RETURN NEW;
   ELSE
      RETURN OLD;
   END IF;
END;
