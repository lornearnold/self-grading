#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""Update Canvas grades for a student-graded assignment."""

import json
import pandas as pd
from canvasapi import Canvas
from argparse import ArgumentParser


def main():
    parser = ArgumentParser(description="Extract rubric evaluations from Canvas assignments.")
    parser.add_argument("-c", "--course_id", help="Canvas course ID", type=int)
    parser.add_argument("-a", "--assignment_id", help="Canvas assignment ID", type=int)
    parser.add_argument("-v", "--verbose", help="Enable verbose output", action="store_true")
    args = parser.parse_args()

    # Check if config.txt exists, otherwise exit with error
    try:
        with open("config.txt", "r") as f:
            # parse JSON configuration file
            config = json.load(f)
            api_key = config["api_key"]
            canvas_url = config["canvas_url"]
    except FileNotFoundError:
        # Prompt the user for the API key and Canvas URL and create config.txt
        print("config.txt not found. Please enter your Canvas API key and URL.")
        canvas_url = input("Enter your Canvas URL (e.g., https://canvas.institution.edu): ")
        api_key = input("Enter your Canvas API key: ")

        # Create config.txt
        with open("config.txt", "w") as f:
            json.dump({"api_key": api_key, "canvas_url": canvas_url}, f)
    except Exception as e:
        print(f"Error reading config.txt: {e}")
        return

    # Create Canvas connection
    canvas = Canvas(canvas_url, api_key)

    # Prompt for course ID if not provided
    if not args.course_id:
        # Search for course by name
        course_name = input("Enter part of the Canvas course name: ")

        if course_name == "":
            # If no course name is provided, list all courses
            matching_courses = [c for c in canvas.get_courses()]
        else:
            # Filter courses by name
            matching_courses = [c for c in canvas.get_courses() if course_name.lower() in c.name.lower()]
        
        if len(matching_courses) > 1:  # Multiple courses found
            for i, c in enumerate(matching_courses):
                print(f"[{i + 1}]: {c.name}")
            
            course_num = int(input("Choose a course by number:")) - 1
            course = matching_courses[course_num]
        elif len(matching_courses) == 1:  # Only one course found
            course = matching_courses[0]
        else:
            print("No matching courses found.")
            return

    else:
        course = canvas.get_course(args.course_id)

    print(f"Selected course: {course.name}")

    # Prompt for assignment ID if not provided
    if not args.assignment_id:
        # Search for assignment by name
        assignment_name = input("Enter part of the Canvas assignment name: ")

        if assignment_name == "":
            # If no assignment name is provided, list all assignments
            matching_assignments = [a for a in course.get_assignments()]
        else:
            matching_assignments = [a for a in course.get_assignments() if assignment_name.lower() in a.name.lower()]
        

        if len(matching_assignments) > 1:
            for i, a in enumerate(matching_assignments):
                print(f"[{i + 1}]: {a.name}")

            assignment_num = int(input("Choose an assignment by number:")) - 1
            assignment = matching_assignments[assignment_num]
        elif len(matching_assignments) == 1:  # Only one assignment found
            assignment = matching_assignments[0]
        else:
            print("No matching assignments found.")
            return

    else:
        assignment = course.get_assignment(args.assignment_id)

    print(f"Selected assignment: {assignment.name}")


if __name__ == "__main__":
    main()
