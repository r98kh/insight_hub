from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as gettext
import re
from croniter import croniter
from datetime import datetime


def validate_cron_expression(value):

    if not value:
        raise ValidationError(gettext('Cron expression cannot be empty.'))
    
    parts = value.strip().split()
    if len(parts) != 5:
        raise ValidationError(gettext('Cron expression must have exactly 5 fields.'))
    
    try:
        cron = croniter(value, datetime.now())
        minute, hour, day, month, day_of_week = parts
    except Exception:
        raise ValidationError(gettext(
            'Invalid cron expression format. '
            'Use format: minute hour day month day_of_week '
            '(e.g., "0 9 * * *" for daily at 9 AM)'
        ))
    
    minute, hour, day, month, day_of_week = parts
    
    _validate_cron_field(minute, 0, 59, 'minute')
    _validate_cron_field(hour, 0, 23, 'hour')
    _validate_cron_field(day, 1, 31, 'day')
    _validate_cron_field(month, 1, 12, 'month')
    _validate_cron_field(day_of_week, 0, 6, 'day_of_week')
    
    _validate_cron_combinations(day, month, day_of_week)


def _validate_cron_field(field_value, min_val, max_val, field_name):
    if field_value == '*':
        return
    
    if '-' in field_value:
        parts = field_value.split('-')
        if len(parts) != 2:
            raise ValidationError(gettext(f'Invalid range format in {field_name} field.'))
        
        try:
            start, end = int(parts[0]), int(parts[1])
            if start < min_val or end > max_val or start > end:
                raise ValidationError(gettext(f'Invalid range in {field_name} field: {start}-{end}'))
        except ValueError:
            raise ValidationError(gettext(f'Invalid range values in {field_name} field.'))
        return
    
    if '/' in field_value:
        parts = field_value.split('/')
        if len(parts) != 2:
            raise ValidationError(gettext(f'Invalid step format in {field_name} field.'))
        
        try:
            step = int(parts[1])
            if step <= 0:
                raise ValidationError(gettext(f'Step value must be positive in {field_name} field.'))
        except ValueError:
            raise ValidationError(gettext(f'Invalid step value in {field_name} field.'))
        return
    
    if ',' in field_value:
        values = field_value.split(',')
        for val in values:
            try:
                num = int(val.strip())
                if num < min_val or num > max_val:
                    raise ValidationError(gettext(f'Value {num} out of range for {field_name} field.'))
            except ValueError:
                raise ValidationError(gettext(f'Invalid value {val} in {field_name} field.'))
        return
    
    try:
        num = int(field_value)
        if num < min_val or num > max_val:
            raise ValidationError(gettext(f'Value {num} out of range for {field_name} field.'))
    except ValueError:
        raise ValidationError(gettext(f'Invalid value {field_value} in {field_name} field.'))


def _validate_cron_combinations(day, month, day_of_week):

    if day != '*' and day_of_week != '*':
        pass
    
    short_months = ['2', '4', '6', '9', '11']
    
    if month in short_months:
        if day != '*':
            try:
                day_num = int(day)
                if month == '2' and day_num > 29:
                    raise ValidationError(gettext('February has maximum 29 days.'))
                elif month in ['4', '6', '9', '11'] and day_num > 30:
                    raise ValidationError(gettext(f'Month {month} has maximum 30 days.'))
            except ValueError:
                pass


def validate_cron_frequency(value):

    if not value:
        return
    
    try:
        cron = croniter(value, datetime.now())
        
        next1 = cron.get_next(datetime)
        next2 = cron.get_next(datetime)
        
        time_diff = next2 - next1
        
        if time_diff.total_seconds() < 60:
            raise ValidationError(gettext(
                'Cron expression is too frequent (less than 1 minute). '
                'This may cause performance issues.'
            ))
        
        elif time_diff.total_seconds() < 300:
            pass
            
    except Exception:
        pass


def get_cron_description(cron_expression):

    if not cron_expression:
        return "No schedule"
    
    try:
        cron = croniter(cron_expression, datetime.now())
        
        next_runs = []
        for _ in range(3):
            next_runs.append(cron.get_next(datetime))
        
        parts = cron_expression.split()
        minute, hour, day, month, day_of_week = parts
        
        description = []
        
        if minute == '*':
            description.append("every minute")
        elif minute == '0':
            description.append("at the top of the hour")
        else:
            description.append(f"at minute {minute}")
        
        if hour == '*':
            description.append("of every hour")
        elif hour == '0':
            description.append("at midnight")
        elif hour == '12':
            description.append("at noon")
        else:
            description.append(f"at hour {hour}")
        
        if day != '*':
            description.append(f"on day {day}")
        
        if month != '*':
            month_names = [
                '', 'January', 'February', 'March', 'April', 'May', 'June',
                'July', 'August', 'September', 'October', 'November', 'December'
            ]
            try:
                month_num = int(month)
                if 1 <= month_num <= 12:
                    description.append(f"in {month_names[month_num]}")
            except ValueError:
                description.append(f"in month {month}")
        
        if day_of_week != '*':
            day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
            try:
                day_num = int(day_of_week)
                if 0 <= day_num <= 6:
                    description.append(f"on {day_names[day_num]}")
            except ValueError:
                description.append(f"on day {day_of_week}")
        
        return " ".join(description)
        
    except Exception:
        return f"Custom schedule: {cron_expression}"


def get_next_run_times(cron_expression, count=5):

    if not cron_expression:
        return []
    
    try:
        cron = croniter(cron_expression, datetime.now())
        next_runs = []
        
        for _ in range(count):
            next_runs.append(cron.get_next(datetime))
        
        return next_runs
        
    except Exception:
        return []


COMMON_CRON_EXPRESSIONS = {
    'every_minute': '* * * * *',
    'every_hour': '0 * * * *',
    'every_day_at_9am': '0 9 * * *',
    'every_weekday_at_9am': '0 9 * * 1-5',
    'every_monday_at_9am': '0 9 * * 1',
    'every_month_first_day': '0 9 1 * *',
    'every_quarter': '0 9 1 1,4,7,10 *',
    'every_year': '0 9 1 1 *',
    'every_5_minutes': '*/5 * * * *',
    'every_15_minutes': '*/15 * * * *',
    'every_30_minutes': '*/30 * * * *',
    'twice_daily': '0 9,21 * * *',
    'weekend_only': '0 9 * * 0,6',
}


def validate_parameter_type(value, expected_type):
    
    import json
    try:
        if expected_type == 'string':
            return isinstance(value, str)
        elif expected_type == 'integer':
            return isinstance(value, int) or (isinstance(value, str) and value.isdigit())
        elif expected_type == 'float':
            return isinstance(value, (int, float)) or (isinstance(value, str) and value.replace('.', '').isdigit())
        elif expected_type == 'boolean':
            return isinstance(value, bool) or value in ['true', 'false', 'True', 'False']
        elif expected_type == 'email':
            return isinstance(value, str) and '@' in value
        elif expected_type == 'url':
            return isinstance(value, str) and value.startswith(('http://', 'https://'))
        elif expected_type == 'json':
            if isinstance(value, str):
                json.loads(value)
            return True
        else:
            return True
    except (ValueError, TypeError):
        return False


def get_common_cron_expressions():
    return COMMON_CRON_EXPRESSIONS


