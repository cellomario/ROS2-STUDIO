"""ROS2 CLI extension for studio command."""
from ros2cli.command import CommandExtension
from ros2_studio.main import main as gui_main


class StudioCommand(CommandExtension):
    """Launch ROS2 Studio GUI for monitoring and bag management."""
    
    def add_arguments(self, parser, cli_name):
        """Add command line arguments."""
        parser.add_argument(
            '--version',
            action='store_true',
            help='Display version information'
        )
        parser.add_argument(
            '--record-config',
            type=str,
            default=None,
            metavar='PATH',
            help='Path to a YAML file with default bag record settings, '
                 'applied as the initial Bag Recorder tab state at launch'
        )

    def main(self, *, parser, args):
        """Execute the command."""
        if args.version:
            print("ROS2 Studio v0.1.0")
            return 0
        
        return gui_main(record_config_path=args.record_config)
